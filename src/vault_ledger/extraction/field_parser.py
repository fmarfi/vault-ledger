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

Those closed sets live in locale_profile.py, one profile per language; the
readers for amounts, dates and paid/unpaid are amounts.py, dates.py and
paid.py. This module only locates which line carries which field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vault_ledger.extraction.amounts import AmountError, first_amount, scan, single_amount
from vault_ledger.extraction.dates import DAY_FIRST, date_matches
from vault_ledger.extraction.llm_fallback import extract_fields_via_llm
from vault_ledger.extraction.locale_profile import (
    AMOUNT_LABEL_PATTERN,
    DUTCH,
    PROFILES,
    LocaleProfile,
    collect,
    words_pattern,
)
from vault_ledger.extraction.paid import STATUS_VALUES, PaidConflict, infer_paid

# A degraded scan often puts a stray mark (a quote, a pipe, a dot) in front
# of a line. Up to two such non-letter marks are skipped when matching a
# label at the start of a line; a stray letter is not, since that would be
# guessing what the word was.
_STRAY = r"^\W{0,2}"

_AMOUNT_LABELS = collect("amount_labels")
_DESCRIPTION_LABELS = collect("description_labels")
_INVOICE_DATE_LABELS = collect("invoice_date_labels")
_STATUS_LABELS = tuple(dict.fromkeys(profile.status_label for profile in PROFILES))

# Tier 1 amount signal: `Label: value` at the start of a line. The fallback
# signal is the same closed set of labels standing anywhere on a line as a
# whole word (AMOUNT_LABEL_PATTERN; the word boundary excludes "Subtotal"
# and "Subtotaal") with an amount on it, e.g. "Total $10.00 USD*" -- common
# on receipts that don't use "Label:" at all.
_AMOUNT_LABEL_COLON_PATTERN = re.compile(
    rf"{_STRAY}({words_pattern(_AMOUNT_LABELS)})\s*:(.*)$", re.IGNORECASE
)

# Fallback description signal: a table-style header line ("Description" or
# "Description Amount Qty", no colon) -- take the next non-empty line as
# the value, since that's the item row underneath the header.
_DESCRIPTION_HEADER_PATTERN = re.compile(
    rf"{_STRAY}{words_pattern(collect('description_headers'))}\b", re.IGNORECASE
)

# The document's own date: one of these labels with the date right behind it.
_INVOICE_DATE_LABEL_PATTERN = re.compile(
    rf"{_STRAY}{words_pattern(_INVOICE_DATE_LABELS)}(?!\w)\s*:?\s*", re.IGNORECASE
)
_DATE_WORD_PATTERN = re.compile(
    "|".join(dict.fromkeys(re.escape(profile.date_word) for profile in PROFILES)), re.IGNORECASE
)

# A line that starts with one of our own field labels is that field, not
# the vendor and not an item row.
_FIELD_LABEL_PATTERN = re.compile(
    _STRAY
    + words_pattern(_AMOUNT_LABELS + _DESCRIPTION_LABELS + _INVOICE_DATE_LABELS + _STATUS_LABELS)
    + r"(?!\w)",
    re.IGNORECASE,
)
_STATUS_LINE_PATTERN = re.compile(
    rf"{_STRAY}{words_pattern(_STATUS_LABELS)}(?!\w)\s*(:)?\s*(.+)$", re.IGNORECASE
)
# `Some label: value` -- the line says in its own words what the value is.
_LABEL_PREFIX_PATTERN = re.compile(rf"{_STRAY}([^:]{{1,40}}):\s*\S")

# Fallback vendor signal: real company names very often end in a legal
# suffix (Inc, LLC, Corp, B.V., ...) -- e.g. a footer address block -- even
# when the actual first line is a greeting/subject line rather than the
# vendor name. Preferred over the first-line guess whenever it's present.
#
# Deliberately checks the LAST word of a line, not "does this line contain
# the substring anywhere" -- a looser substring/regex search also matches a
# suffix word used in ordinary prose (e.g. "...your Example Corp
# subscription...", which is not a company-name line at all), and a real
# fixture caught exactly that false positive during development.
_COMPANY_SUFFIXES = frozenset().union(*(profile.legal_suffixes for profile in PROFILES))
_CUSTOMER_LABELS = frozenset().union(*(profile.customer_labels for profile in PROFILES))

# A narrow, stable structural pattern -- how documents render pagination or
# a bare document-type label, with or without its number ("Page 1 of 1",
# "Invoice", "INVOICE #1042", "FACTUUR 2026-0417") -- not an open-ended
# list of content phrasings. There are only so many ways to write "page 1
# of 1"; this doesn't have the whack-a-mole problem an open-ended phrase
# list would.
_BOILERPLATE_LINE_PATTERN = re.compile(
    "^(?:"
    + "|".join(
        rf"{page}\s+\d+\s+{of}\s+\d+" for page, of in (profile.page_words for profile in PROFILES)
    )
    + rf"|{words_pattern(collect('document_words'))}"
    + rf"(?:\s+(?:{words_pattern(collect('number_words'))}\.?)?\s*[#:]?\s*[\w/-]*\d[\w/-]*)?"
    + ")$",
    re.IGNORECASE,
)


class FieldParseError(Exception):
    """Raised when a required field (vendor, amount) cannot be located."""


@dataclass(frozen=True)
class ExtractedFields:
    vendor: str
    description: str
    date: str | None
    amount: float
    paid: bool


def _find_labeled_value(
    lines: list[str], labels: tuple[str, ...], *, strict: bool = False
) -> str | None:
    """First `Label: value` match. With strict=True, several lines carrying
    conflicting values for these labels raise instead of silently returning
    the first -- same escalate-don't-guess rule as _find_vendor."""
    pattern = re.compile(rf"{_STRAY}({words_pattern(labels)})\s*:(.*)$", re.IGNORECASE)
    values = []
    by_label: dict[str, set[str]] = {}
    for line in lines:
        match = pattern.match(line)
        if match:
            value = match.group(2).strip()
            values.append(value)
            by_label.setdefault(match.group(1).lower(), set()).add(_normalize_for_comparison(value))
    if not values:
        return None
    # Conflict = the same label repeated with different values.
    if strict:
        for label, distinct in by_label.items():
            if len(distinct) > 1:
                raise FieldParseError(f"conflicting values found for '{label}'")
    return values[0]


def _normalize_for_comparison(value: str) -> str:
    amount = first_amount(value)
    if amount is not None:
        return str(amount)
    return " ".join(value.lower().split())


def _shows_language(profile: LocaleProfile, lines: list[str]) -> bool:
    """Whether the document carries one of this language's own field labels."""
    labels = profile.amount_labels + profile.description_labels + profile.invoice_date_labels
    pattern = re.compile(rf"{_STRAY}{words_pattern(labels)}(?!\w)", re.IGNORECASE)
    return any(pattern.match(line) for line in lines)


def document_date_order(raw_text: str) -> str | None:
    """The day/month order the document itself settles: day first when it
    carries Dutch field labels (Dutch never writes the month first). None
    when the document doesn't say -- an English document can be either."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return DAY_FIRST if _shows_language(DUTCH, lines) else None


def _ends_in_legal_suffix(line: str, lines: list[str]) -> bool:
    words = line.split()
    last = words[-1].strip(".,").lower()
    if last in _COMPANY_SUFFIXES:
        return True
    # "Reno, NV" and "...see attached C.V." are not companies. These forms
    # count only on a document in their own language, and not after a comma
    # (Dutch names carry no comma before the legal form; US states do).
    after_comma = len(words) > 1 and words[-2].endswith(",")
    return any(
        last in profile.legal_suffixes_local and not after_comma and _shows_language(profile, lines)
        for profile in PROFILES
    )


def _find_vendor(lines: list[str]) -> str | None:
    bare, labeled = [], []
    for line in lines:
        if not _ends_in_legal_suffix(line, lines):
            continue
        label = _LABEL_PREFIX_PATTERN.match(line)
        if label is None:
            bare.append(line)
        elif label.group(1).strip(" .").lower() not in _CUSTOMER_LABELS:
            labeled.append(line)
        # else: "Bill to: ... Inc" / "Aan: ... B.V." names the customer.
    if len(bare) == 1 and not labeled:
        return bare[0]
    if bare or labeled:
        # More than one candidate company name, or a company named under a
        # label that doesn't say which party it is ("Remit payments to: XYZ
        # Inc") -- picking whichever happened to match first is exactly the
        # kind of silent guess this module's docstring says not to make.
        # Escalate instead.
        return None

    # No company-suffix line found. Fallback: vendor name is near the top
    # (Report 1's own suggested heuristic) -- true for a business-
    # letterhead-style document, though not for a transactional receipt
    # where line one is a greeting/subject or generic document metadata,
    # nor when line one is a labelled field or a table header.
    first = lines[0]
    if (
        _BOILERPLATE_LINE_PATTERN.match(first)
        or _LABEL_PREFIX_PATTERN.match(first)
        or _FIELD_LABEL_PATTERN.match(first)
        or _DESCRIPTION_HEADER_PATTERN.match(first)
    ):
        return None
    return first


def _find_description_raw(lines: list[str]) -> str | None:
    # A labelled value without a single letter ("Artikelen: 3") is a count,
    # not a description.
    worded = [line for line in lines if re.search(r"[^\W\d_]", line.partition(":")[2])]
    labeled = _find_labeled_value(worded, _DESCRIPTION_LABELS, strict=True)
    if labeled is not None:
        return labeled

    for i, line in enumerate(lines):
        if _DESCRIPTION_HEADER_PATTERN.match(line) and i + 1 < len(lines):
            below = lines[i + 1]
            if _LABEL_PREFIX_PATTERN.match(below) or _FIELD_LABEL_PATTERN.match(below):
                # The line below is another field, not an item row -- so
                # this was a label that lost its colon ("Items Coffee, ...")
                # and where its value starts is not known. Escalate.
                return None
            return below
    return None


def _read_amount(raw: str) -> float:
    try:
        return single_amount(raw)
    except AmountError as error:
        raise FieldParseError(str(error)) from None


def _find_amount_raw(lines: list[str]) -> str | None:
    candidates: list[tuple[str | None, str]] = []
    for line in lines:
        labeled = _AMOUNT_LABEL_COLON_PATTERN.match(line)
        if labeled:
            candidates.append((labeled.group(1).lower(), labeled.group(2).strip()))
        elif AMOUNT_LABEL_PATTERN.search(line) and scan(line):
            candidates.append((None, line))
    if not candidates:
        return None

    # Every candidate is read, and every one must be readable: a total line
    # with two amounts on it, or one that can't be read safely, raises.
    values = {raw: _read_amount(raw) for _, raw in candidates}
    if len(set(values.values())) == 1:
        return candidates[0][1]

    by_label: dict[str, set[float]] = {}
    for label, raw in candidates:
        if label is not None:
            by_label.setdefault(label, set()).add(values[raw])
    for label, distinct in by_label.items():
        if len(distinct) > 1:
            raise FieldParseError(f"conflicting values found for '{label}'")
    # Different total lines with different values: genuinely ambiguous -- a
    # real invoice had both "Total excluding tax €20.66" and "Total €25.00",
    # and others carry "Total: 100.00" next to "Total incl. VAT: 121.00" or
    # "Amount Due: 40.00". Picking one via a hardcoded list of qualifier
    # phrases ("excluding", "before tax", ...) is exactly the whack-a-mole
    # this project keeps running into: infinite possible phrasings, always
    # missing the next one. Refuse to guess instead and let the caller
    # escalate to the LLM tier, which reads the whole document.
    return None


def _find_date(raw_text: str) -> str | None:
    """The date under an invoice-date label; failing that, the only date in
    the document that is not labelled as some other date. Several different
    candidates give None -- which of them is the document date is not guessed."""
    labeled, loose = [], []
    for line in (line.strip() for line in raw_text.splitlines()):
        label = _INVOICE_DATE_LABEL_PATTERN.match(line)
        for match in date_matches(line):
            before = line[: match.start()]
            if label and match.start() == label.end():
                labeled.append(match.group(0))
            elif ":" not in before and not _DATE_WORD_PATTERN.search(before):
                loose.append(match.group(0))
            # else: "Due date: ...", "Vervaldatum ...", "Policy No: ..." --
            # labelled as something other than the document date.
    for found in (labeled, loose):
        if len(set(found)) == 1:
            return found[0]
        if found:
            return None
    return None


def _find_status(lines: list[str]) -> str | None:
    """`Status: value`; without the colon (lost in OCR) only when the value
    is one of the known status words."""
    for line in lines:
        match = _STATUS_LINE_PATTERN.match(line)
        if match and (match.group(1) or match.group(2).strip().upper() in STATUS_VALUES):
            return match.group(2).strip()
    return None


def _infer_paid(raw_text: str, status_raw: str | None, amount: float | None = None) -> bool | None:
    """Returns None when there's no confident signal either way -- distinct
    from a real False, so callers can tell "genuinely unpaid" apart from
    "we don't actually know" (see parse_fields: this heuristic's confident
    answers should be trusted even when the LLM tier ran for a different
    field). Its one ambiguous case -- the document states both paid and
    unpaid -- raises, like every other ambiguity in this module."""
    try:
        return infer_paid(raw_text, status_raw, amount)
    except PaidConflict as conflict:
        raise FieldParseError(str(conflict)) from None


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
        raise FieldParseError("could not locate a single amount/total field")
    amount = _read_amount(amount_raw)

    date = _find_date(raw_text)

    paid = _infer_paid(raw_text, _find_status(lines), amount)
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
        # Trust _infer_paid over the LLM's guess whenever it found a real
        # signal. A real invoice caught the LLM getting this wrong (said
        # paid=True for a document explicitly reading "€25.00 due ... Pay
        # online"). A document that states both paid and unpaid raises
        # here again: the model does not get to settle that.
        confident_paid = _infer_paid(raw_text, _find_status(lines), llm_result["amount"])
        if confident_paid is not None:
            llm_result = {**llm_result, "paid": confident_paid}

        # Same for the date: a labelled invoice date beats the model's pick.
        located_date = _find_date(raw_text)
        if located_date is not None:
            llm_result = {**llm_result, "date": located_date}

        return ExtractedFields(**llm_result)
