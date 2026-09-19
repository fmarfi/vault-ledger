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
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import TypedDict

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:1.5b-instruct"
TIMEOUT_SECONDS = 60  # CPU-only inference on modest hardware can be slow

_AMOUNT_PATTERN = re.compile(r"\$?\s*([0-9][0-9,]*\.[0-9]{2})")
_TOTAL_WORD_PATTERN = re.compile(r"\b(total|amount\s+due)\b", re.IGNORECASE)  # \b excludes "Subtotal"


def _amounts_on_total_lines(raw_text: str) -> set[str]:
    amounts: set[str] = set()
    for line in raw_text.splitlines():
        if _TOTAL_WORD_PATTERN.search(line):
            amounts.update(m.replace(",", "") for m in _AMOUNT_PATTERN.findall(line))
    return amounts

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
        {"model": MODEL_NAME, "prompt": prompt, "format": "json", "stream": False}
    ).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )

    try:
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

    amount_match = _AMOUNT_PATTERN.search(str(parsed.get("amount", "")))
    if amount_match is None:
        logger.warning("LLM fallback rejected: no parseable amount in %r", parsed.get("amount"))
        return None
    claimed_amount = amount_match.group(1).replace(",", "")

    real_amounts = {m.replace(",", "") for m in _AMOUNT_PATTERN.findall(raw_text)}
    if claimed_amount not in real_amounts:
        logger.warning("LLM fallback rejected: amount %s is not in the document text", claimed_amount)
        return None  # the model named a number that isn't actually in the document

    # Real-but-wrong-line check: if the document has explicit "Total" /
    # "Amount due" lines with amounts, the claim must be one of those. A
    # model echoing a tax, cash-tendered, or line-item figure otherwise
    # passes grounding.
    total_line_amounts = _amounts_on_total_lines(raw_text)
    if total_line_amounts and claimed_amount not in total_line_amounts:
        logger.warning(
            "LLM fallback rejected: amount %s is in the text but not on a total line",
            claimed_amount,
        )
        return None

    return {
        "vendor": vendor,
        "description": description,
        "date": parsed.get("date") or None,
        "amount": float(claimed_amount),
        "paid": bool(parsed.get("paid", False)),
    }
