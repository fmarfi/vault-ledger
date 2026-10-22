"""Local LLM fallback for field extraction -- last resort, after every
heuristic in field_parser.py has already failed.

Requires Ollama running locally (`ollama serve`, automatic after install)
with a small model pulled (`ollama pull qwen2.5:1.5b-instruct` or similar --
kept deliberately small; this machine's 8GB RAM / low-power CPU is close to
a real lower bound, not just "slower than cloud"). 100% local: Ollama's
HTTP API is bound to localhost, and no request here ever leaves the
machine. This is the same architecture a per-company deployment would use
-- Ollama runs on that company's own server, the model is downloaded once
(a generic public model, not customer data) and cached on local disk, and
every extraction call after that is offline inference against the cache.

Fails closed, not open: if Ollama isn't running, the model isn't pulled, or
the response can't be trusted, this returns None and field_parser.py raises
its normal, clear FieldParseError -- it never raises its own exception up
to the caller, and it never lets the model's output through unchecked.

Anti-hallucination check: the model's claimed amount must be a currency
value that actually appears in the source text. It is never trusted to
report a correct number on its own -- only trusted to point at which
already-real number is the total, mirroring the same "validate, don't just
trust the model" principle already applied to the rules layer (VERAFI,
Report 4 SS2).

The same holds for every other field it proposes: the vendor must stand in
the text, the description must be made of words from the text, the date
must be a calendar-valid date that stands in the text (otherwise it is
dropped to None), and "paid" is only believed when the text itself carries
evidence of payment (otherwise it is False).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.error
import urllib.request
from typing import TypedDict

from vault_ledger.extraction.amounts import AmountError, find_amounts, scan, single_amount
from vault_ledger.extraction.dates import find_dates
from vault_ledger.extraction.locale_profile import AMOUNT_LABEL_PATTERN
from vault_ledger.extraction.paid import has_paid_evidence

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:1.5b-instruct"
TIMEOUT_SECONDS = 60  # CPU-only inference on modest hardware can be slow

# Batch processing (batch.py) runs documents concurrently, but this machine
# has one small model on 8GB RAM / 2 cores -- two inferences at once would
# fight over the same limited memory and likely be slower than one at a
# time, not faster. This serializes tier-3 calls specifically: tiers 1-2
# still run fully in parallel across a batch, only the LLM call itself
# queues, and only for documents that actually needed it.
_INFERENCE_LOCK = threading.Lock()

# A total label with a colon and digits behind it: a total was printed there,
# whether or not it can be read.
_LABELED_TOTAL_PATTERN = re.compile(rf"{AMOUNT_LABEL_PATTERN.pattern}\s*:.*[0-9]", re.IGNORECASE)
_WORD_PATTERN = re.compile(r"[^\W_]+")


def _amounts_on_total_lines(raw_text: str) -> tuple[set[float], bool]:
    """The amounts on "Total" / "Amount due" lines that hold exactly one
    amount, and whether any total line could not be read that safely (two
    amounts on it, a doubtful reading, a labelled total with no amount)."""
    amounts: set[float] = set()
    unsafe = False
    for line in raw_text.splitlines():
        if not AMOUNT_LABEL_PATTERN.search(line):
            continue
        readings = scan(line)
        values = {reading.value for reading in readings if reading.doubt is None}
        if any(reading.doubt for reading in readings) or len(values) > 1:
            unsafe = True
        elif values:
            amounts.update(values)
        elif _LABELED_TOTAL_PATTERN.search(line):
            unsafe = True
    return amounts, unsafe


def _normalized(text: str) -> str:
    return " ".join(text.lower().split())


def _words(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


_PROMPT_TEMPLATE = """Extract fields from this business document text. Respond with ONLY a JSON object, no other text, in this exact shape:
{{"vendor": "...", "description": "...", "date": "...", "amount": "...", "paid": true or false}}

Rules:
- "vendor": the company/business name that issued this document.
- "description": what was purchased or paid for, in a few words.
- "date": the document date, exactly as it appears in the text.
- "amount": the total amount as it appears in the text (e.g. "10.00") -- the final total, not a subtotal or tax line.
- "paid": true if the document indicates payment was already made/received, false if a payment is owed/due.

Document text:
---
{text}
---
"""


class LlmExtractedFields(TypedDict):
    vendor: str
    description: str
    date: str | None
    amount: float
    paid: bool


def extract_fields_via_llm(raw_text: str) -> LlmExtractedFields | None:
    prompt = _PROMPT_TEMPLATE.format(text=raw_text[:4000])  # keep the prompt small; slow CPU

    payload = json.dumps(
        {
            "model": MODEL_NAME,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            # Keep the model resident so only the first call pays the load;
            # cap output (the JSON reply is ~100 tokens); 4096 context because
            # a 4000-char digit-heavy invoice can reach ~2k tokens and Ollama
            # silently drops the oldest tokens (the instructions) on overflow.
            "keep_alive": "10m",
            "options": {"temperature": 0, "num_predict": 200, "num_ctx": 4096},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )

    try:
        with _INFERENCE_LOCK:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                body = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        # Ollama not running / not reachable / too slow -- unavailable, not a bug.
        logger.warning("LLM fallback unavailable (%s): %s", type(exc).__name__, exc)
        return None

    try:
        parsed = json.loads(body["response"])
    except (KeyError, json.JSONDecodeError, TypeError):
        logger.warning("LLM fallback returned a response that is not valid JSON")
        return None
    if not isinstance(parsed, dict):
        logger.warning("LLM fallback returned JSON that is not an object")
        return None

    vendor = parsed.get("vendor")
    description = parsed.get("description")
    if not vendor or not description:
        logger.warning("LLM fallback rejected: missing vendor or description")
        return None
    if not isinstance(vendor, str) or not isinstance(description, str):
        logger.warning("LLM fallback rejected: vendor or description is not text")
        return None

    # Grounding for the two text fields. The vendor is a name and must stand
    # in the document as written; the description is asked for "in a few
    # words", so it may join words from several lines but may not bring a
    # word of its own.
    if _normalized(vendor) not in _normalized(raw_text):
        logger.warning("LLM fallback rejected: vendor %r is not in the document text", vendor)
        return None
    if not _words(description) or _words(description) - _words(raw_text):
        logger.warning("LLM fallback rejected: description uses words not in the document text")
        return None

    try:
        claimed_amount = single_amount(str(parsed.get("amount", "")))
    except AmountError:
        logger.warning("LLM fallback rejected: no parseable amount in %r", parsed.get("amount"))
        return None

    real_amounts = set(find_amounts(raw_text))
    if claimed_amount not in real_amounts:
        logger.warning("LLM fallback rejected: amount %s is not in the document text", claimed_amount)
        return None  # the model named a number that isn't actually in the document

    # Real-but-wrong-line check: if the document has explicit "Total" /
    # "Amount due" lines with amounts, the claim must be one of those. A
    # model echoing a tax, cash-tendered, or line-item figure otherwise
    # passes grounding.
    # A total line that can't be read safely (two amounts on it, a number
    # split by a gap) supports no claim at all: the model would be picking
    # between figures this module could not tell apart either.
    total_line_amounts, unsafe_total_line = _amounts_on_total_lines(raw_text)
    if claimed_amount not in total_line_amounts and (total_line_amounts or unsafe_total_line):
        logger.warning(
            "LLM fallback rejected: amount %s is in the text but not on a readable total line",
            claimed_amount,
        )
        return None

    # The date is optional, so a date that fails is dropped, not the reply.
    document_dates = set(find_dates(raw_text))
    claimed_dates = set(find_dates(str(parsed.get("date") or "")))
    date = None
    if len(claimed_dates) == 1 and claimed_dates <= document_dates:
        (date,) = claimed_dates
    elif parsed.get("date"):
        logger.warning(
            "LLM fallback dropped date %r: not a date found in the document text", parsed.get("date")
        )

    paid = parsed.get("paid") is True
    if paid and not has_paid_evidence(raw_text, total=claimed_amount):
        logger.warning("LLM fallback set paid to False: the document shows no evidence of payment")
        paid = False

    return {
        "vendor": vendor,
        "description": description,
        "date": date,
        "amount": claimed_amount,
        "paid": paid,
    }
