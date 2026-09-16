"""Field parsing: raw OCR text -> vendor, description, date, amount, paid.

Report 1, item 3 -- the step flagged as most likely to silently undercut the
two-field classifier gain. Vendor and description MUST come out as two
separate fields, never concatenated.

Three tiers, in order: an exact match against our synthetic samples'
labeled convention (`Label: value`); then a looser real-world heuristic
fallback for documents that don't follow that convention (table headers
with no colon, "Total" with no label, vendor name buried in a footer
rather than on line one); then, only if both of those fail, a local LLM
fallback (`extraction/llm_fallback.py`) that reads the whole document and
proposes fields, with its claimed amount cross-checked against real
currency values in the source text so it can't hallucinate a number.

Honest limitation: tiers 1-2 are heuristics discovered from real documents
encountered during development (see git history), not a general solution.
They widen what parses successfully; they don't guarantee it. Tier 3
generalizes further but is slower (seconds, not milliseconds) and requires
Ollama running locally -- see llm_fallback.py's module docstring.

A design rule that came out of a real bug (see git history: a real invoice
had both "Total excluding tax" and "Total" lines; naively taking whichever
matched first picked the wrong one): when a tier-2 heuristic finds more
than one plausible candidate for a field, it must NOT guess between them
by hardcoding a list of disambiguating phrases ("excluding", "before tax",
...) -- that list is always incomplete and always one phrasing behind.
Instead, treat multiple candidates the same as zero: raise, and let tier 3
resolve it, since the LLM reads the whole document rather than pattern-
matching one line at a time. Bounded, stable lexical facts (currency
symbols, legal-entity suffixes, month names) are fine to enumerate --
they're closed sets. Open-ended judgment calls about which of several
plausible values is correct are not, and should escalate instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vault_ledger.extraction.llm_fallback import extract_fields_via_llm

_AMOUNT_LABELS = ("Amount Due", "Total Amount", "Total")
_DESCRIPTION_LABELS = ("Description", "Service", "Items")

_AMOUNT_PATTERN = re.compile(r"\$?\s*([0-9][0-9,]*\.[0-9]{2})")
_DATE_PATTERN = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
_ISO_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_MONTH_NAMES = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
    "|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
_MONTH_NAME_DATE_PATTERN = re.compile(
    rf"\b(({_MONTH_NAMES})\.?\s+\d{{1,2}},?\s+\d{{4}})\b", re.IGNORECASE
)

# Fallback amount signal: a line with the standalone word "Total" (word
# boundary excludes "Subtotal") and a currency amount on it, e.g.
# "Total $10.00 USD*" -- common on receipts that don't use "Label:" at all.
_TOTAL_WORD_PATTERN = re.compile(r"\btotal\b", re.IGNORECASE)

# Fallback description signal: a table-style header line ("Description" or
# "Description Amount Qty", no colon) -- take the next non-empty line as
# the value, since that's the item row underneath the header.
_DESCRIPTION_HEADER_PATTERN = re.compile(r"^(description|items?|service)\b", re.IGNORECASE)

# Fallback vendor signal: real company names very often end in a legal
# suffix (Inc, LLC, Corp, ...) -- e.g. a footer address block -- even when
# the actual first line is a greeting/subject line rather than the vendor
# name. Preferred over the first-line guess whenever it's present.
#
# Deliberately checks the LAST word of a line, not "does this line contain
# the substring anywhere" -- a looser substring/regex search also matches a
# suffix word used in ordinary prose (e.g. "...your Example Corp
# subscription...", which is not a company-name line at all), and a real
# fixture caught exactly that false positive during development.
_COMPANY_SUFFIXES = {
    "inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation",
    "company", "co", "gmbh", "plc",
}

# A narrow, stable structural pattern -- how documents render pagination or
# a bare document-type label -- not an open-ended list of content
# phrasings. There are only so many ways to write "page 1 of 1"; this
# doesn't have the whack-a-mole problem an open-ended phrase list would.
_BOILERPLATE_LINE_PATTERN = re.compile(r"^(page\s+\d+\s+of\s+\d+|invoice|receipt)$", re.IGNORECASE)

# Fallback paid/unpaid signal, used only when there's no explicit
# "Status: PAID/UNPAID" line. Deliberately conservative: an unmatched
# document defaults to unpaid (Accounts Payable) rather than guessing paid.
_PAID_KEYWORDS = ("receipt", "payment received", "received payment", "charged to", "paid in full")
_UNPAID_KEYWORDS = ("amount due", "balance due", "please pay", "payment due", "invoice due")


class FieldParseError(Exception):
    """Raised when a required field (vendor, amount) cannot be located."""


@dataclass(frozen=True)
class ExtractedFields:
    vendor: str
    description: str
    date: str | None
    amount: float
    paid: bool


def _find_labeled_value(lines: list[str], labels: tuple[str, ...]) -> str | None:
    for line in lines:
        for label in labels:
            prefix = f"{label}:"
            if line.lower().startswith(prefix.lower()):
                return line[len(prefix):].strip()
    return None


def _find_vendor(lines: list[str]) -> str | None:
    suffix_matches = [
        line
        for line in lines
        if (words := line.split()) and words[-1].strip(".,").lower() in _COMPANY_SUFFIXES
    ]
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    if len(suffix_matches) > 1:
        # More than one candidate company name (e.g. a "Bill To: ... Inc"
        # line as well as the actual vendor's "... LLC" line) -- picking
        # whichever happened to match first is exactly the kind of silent
        # guess this module's docstring says not to make. Escalate instead.
        return None

    # No company-suffix line found. Fallback: vendor name is near the top
    # (Report 1's own suggested heuristic) -- true for a business-
    # letterhead-style document, though not for a transactional receipt
    # where line one is a greeting/subject or generic document metadata.
    if _BOILERPLATE_LINE_PATTERN.match(lines[0]):
        return None
    return lines[0]


def _find_description_raw(lines: list[str]) -> str | None:
    labeled = _find_labeled_value(lines, _DESCRIPTION_LABELS)
    if labeled is not None:
        return labeled

    for i, line in enumerate(lines):
        if _DESCRIPTION_HEADER_PATTERN.match(line) and i + 1 < len(lines):
            return lines[i + 1]
    return None


def _find_amount_raw(lines: list[str]) -> str | None:
    labeled = _find_labeled_value(lines, _AMOUNT_LABELS)
    if labeled is not None:
        return labeled

    candidates = [
        line for line in lines if _TOTAL_WORD_PATTERN.search(line) and _AMOUNT_PATTERN.search(line)
    ]
    if len(candidates) == 1:
        return candidates[0]
    # Zero candidates: not found, nothing to guess from. More than one:
    # genuinely ambiguous -- a real invoice had both "Total excluding tax
    # €20.66" and "Total €25.00", and picking one via a hardcoded list of
    # qualifier phrases ("excluding", "before tax", ...) is exactly the
    # whack-a-mole this project keeps running into: infinite possible
    # phrasings, always missing the next one. Refuse to guess instead and
    # let the caller escalate to the LLM tier, which reads the whole
    # document and correctly grounds to the real total (verified).
    return None


def _find_date(raw_text: str) -> str | None:
    match = (
        _DATE_PATTERN.search(raw_text)
        or _ISO_DATE_PATTERN.search(raw_text)
        or _MONTH_NAME_DATE_PATTERN.search(raw_text)
    )
    return match.group(1) if match else None


def _infer_paid(raw_text: str, status_raw: str | None) -> bool | None:
    """Returns None when there's no confident signal either way -- distinct
    from a real False, so callers can tell "genuinely unpaid" apart from
    "we don't actually know" (see parse_fields: this heuristic has no
    ambiguous-candidates failure mode the way vendor/amount do, so its
    confident answers should be trusted even when the LLM tier ran for a
    different field)."""
    if status_raw:
        return status_raw.strip().upper() == "PAID"

    lowered = raw_text.lower()
    if any(keyword in lowered for keyword in _UNPAID_KEYWORDS):
        return False
    if any(keyword in lowered for keyword in _PAID_KEYWORDS):
        return True
    return None


def _parse_fields_heuristic(lines: list[str], raw_text: str) -> ExtractedFields:
    """Tiers 1-2: exact synthetic-label match, then real-world fallbacks.
    Raises FieldParseError if a required field can't be located this way.
    """
    vendor = _find_vendor(lines)
    if vendor is None:
        raise FieldParseError("could not confidently determine the vendor")

    description = _find_description_raw(lines)
    if description is None:
        raise FieldParseError("could not locate a description/service/items field")

    amount_raw = _find_amount_raw(lines)
    if amount_raw is None:
        raise FieldParseError("could not locate an amount/total field")
    amount_match = _AMOUNT_PATTERN.search(amount_raw)
    if amount_match is None:
        raise FieldParseError(f"could not parse a currency amount from '{amount_raw}'")
    amount = float(amount_match.group(1).replace(",", ""))

    date = _find_date(raw_text)

    status_raw = _find_labeled_value(lines, ("Status",))
    paid = _infer_paid(raw_text, status_raw)
    if paid is None:
        paid = False  # conservative default when genuinely ambiguous

    return ExtractedFields(
        vendor=vendor,
        description=description,
        date=date,
        amount=amount,
        paid=paid,
    )


def parse_fields(raw_text: str) -> ExtractedFields:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        raise FieldParseError(
            "OCR found no readable text in this image. This usually means the "
            "source image is too low-resolution, too blurry, or too small "
            "(well under ~900px on the short side) for Tesseract to read -- "
            "not a bug in field parsing. Try a clearer, higher-resolution "
            "photo or scan of the document."
        )

    try:
        return _parse_fields_heuristic(lines, raw_text)
    except FieldParseError as heuristic_error:
        # Tier 3: local LLM, only reached when tiers 1-2 both fail. Fails
        # closed (returns None) if Ollama isn't running/reachable or its
        # output can't be trusted -- in which case the original, clearer
        # heuristic error is what the caller sees, not a new one.
        llm_result = extract_fields_via_llm(raw_text)
        if llm_result is None:
            raise heuristic_error

        # Escalating for one field (e.g. an ambiguous amount) shouldn't
        # throw away a field our own heuristic already handles reliably.
        # _infer_paid has no ambiguous-candidates failure mode -- it's a
        # keyword-presence check, either confident or not -- so trust it
        # over the LLM's guess whenever it found a real signal. A real
        # invoice caught the LLM getting this wrong (said paid=True for a
        # document explicitly reading "€25.00 due ... Pay online").
        status_raw = _find_labeled_value(lines, ("Status",))
        confident_paid = _infer_paid(raw_text, status_raw)
        if confident_paid is not None:
            llm_result = {**llm_result, "paid": confident_paid}

        return ExtractedFields(**llm_result)
