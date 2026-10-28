"""L0 normalization (spec 6.1): clean counterparty and description text.

Removes payment-terminal and payment-provider prefixes, references, IBANs and
long numbers so the model sees the merchant, not the transport.
"""
from __future__ import annotations

import re

# Prefixes banks and payment providers put in front of the real counterparty.
_PREFIXES = [
    r"bea", r"gea", r"betaalautomaat", r"pin", r"pinbetaling", r"ideal", r"sepa incasso",
    r"sepa overboeking", r"incasso", r"overboeking", r"bkg", r"ccv\*", r"sumup\s*\*",
    r"zettle_?\*", r"sq\s*\*", r"pp\*", r"paypal \*", r"mollie\*", r"adyen\*", r"stripe\*",
]
_PREFIX_RE = re.compile(r"^(?:(?:" + "|".join(_PREFIXES) + r")[\s,:\-*]*)+", re.IGNORECASE)
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7,}\b", re.IGNORECASE)
_LONG_NUM_RE = re.compile(r"\b\d{5,}\b")
_STORE_NUM_RE = re.compile(r"\b\d{2,4}\b")
_REF_RE = re.compile(r"\b(?:kenmerk|ref(?:erentie)?|transactie|trn|mandaat|machtiging)[:\s]*\S+", re.IGNORECASE)
_TERMINAL_RE = re.compile(r"\bpas\s*\d+\b|\bterm(?:inal)?\s*\w+\b|\b\d{2}[.:]\d{2}\s*uur\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b")
_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s&.'-]", re.UNICODE)


def _clean(text: str | None) -> str:
    if not text:
        return ""
    t = _IBAN_RE.sub(" ", text)
    t = _REF_RE.sub(" ", t)
    t = _TERMINAL_RE.sub(" ", t)
    t = _DATE_RE.sub(" ", t)
    t = _LONG_NUM_RE.sub(" ", t)
    t = _PUNCT_RE.sub(" ", t)
    return _SPACE_RE.sub(" ", t).strip().lower()


def normalize_counterparty(name: str | None) -> str:
    if not name:
        return ""
    t = _PREFIX_RE.sub("", name.strip())
    # Store / terminal numbers in a name ("ALBERT HEIJN 1234") carry no merchant signal.
    t = _STORE_NUM_RE.sub(" ", t)
    return _clean(t)


def normalize_description(text: str | None) -> str:
    if not text:
        return ""
    return _clean(_PREFIX_RE.sub("", text.strip()))
