"""Demo mode seed data (VAULT_DEMO, see the README).

Everything in this file is INVENTED: the vendors are plausible names for a
small Dutch startup's suppliers, but no such invoices exist. It is written
into a throwaway demo user's own directory, and only through the same code
paths a real document takes -- `pipeline.propose_entry` (classifier,
confidence gate, rules layer), `construct_entry`, `append_entry`, `enqueue`,
`record_correction` -- never by writing CSV rows by hand, so every seeded
entry satisfies the balance invariant.

What is real and what is set by hand:

- Posted history (LEDGER_SEED): the account each document was posted to is
  ours, but the confidence, and whether the entry counts as "corrected", come
  from running the real classifier on it. So the "accepted as-is" rate on the
  Documents page is the model's true behaviour on this invented data.
- Review queue (QUEUE_SEED): items with `illustrative_confidence=None` carry
  the real classifier's account, confidence and review flag. Items WITH an
  illustrative confidence are hand-set, see the note on QUEUE_SEED.

Amounts are plain numbers at euro scale. The app has no currency setting yet
(the UI prints a fixed symbol), so nothing here stores a currency.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable

from vault_ledger import coa, userdata
from vault_ledger.confidence_gate import needs_manual_review
from vault_ledger.corrections import record_correction
from vault_ledger.ledger import append_entry
from vault_ledger.pipeline import propose_entry
from vault_ledger.queue import enqueue
from vault_ledger.rules.entry_rules import construct_entry


@dataclass(frozen=True)
class LedgerSeed:
    days_ago: int
    vendor: str
    description: str
    amount: float
    paid: bool
    account: str


@dataclass(frozen=True)
class QueueSeed:
    days_ago: int
    vendor: str
    description: str
    amount: float
    paid: bool
    # None = use the real classifier's output untouched.
    illustrative_account: str | None = None
    illustrative_confidence: float | None = None


_RENT = coa.RENT_EXPENSE
_UTIL = coa.UTILITIES_EXPENSE
_SOFT = coa.SOFTWARE_SUBSCRIPTIONS_EXPENSE
_TRAVEL = coa.TRAVEL_EXPENSE
_PROF = coa.PROFESSIONAL_SERVICES_EXPENSE
_OFFICE = coa.OFFICE_SUPPLIES_EXPENSE
_OTHER = coa.GENERAL_EXPENSE

# Three months of posted history, every default expense account represented.
# `paid` decides the credit side when the entry is constructed (Cash/Bank vs
# Accounts Payable); ledger.csv itself does not store it.
LEDGER_SEED: tuple[LedgerSeed, ...] = (
    LedgerSeed(0, "Albert Heijn", "Coffee and office snacks", 31.42, True, _OTHER),
    LedgerSeed(2, "NS Reizigers B.V.", "Train travel for client site visit", 43.20, True, _TRAVEL),
    LedgerSeed(3, "Slack Technologies Inc", "Monthly team messaging subscription", 52.50, True, _SOFT),
    LedgerSeed(5, "KPN Zakelijk", "Monthly internet and phone service", 89.00, True, _UTIL),
    LedgerSeed(6, "Van Dijk Accounting", "Quarterly VAT filing preparation", 425.00, False, _PROF),
    LedgerSeed(8, "Spaces Zuidas B.V.", "Monthly office rent payment", 1850.00, True, _RENT),
    LedgerSeed(10, "GitHub, Inc.", "GitHub Team - month", 37.00, True, _SOFT),
    LedgerSeed(12, "Eneco Zakelijk", "Electricity and gas usage", 214.37, False, _UTIL),
    LedgerSeed(15, "Google Ireland Ltd", "Google Workspace monthly subscription", 69.00, True, _SOFT),
    LedgerSeed(18, "Office Centre", "Bulk copy paper order", 64.95, True, _OFFICE),
    LedgerSeed(20, "Odido Business", "Monthly mobile phone service", 62.50, True, _UTIL),
    LedgerSeed(22, "Q-Park Parking Garage", "Monthly parking pass renewal", 145.00, True, _TRAVEL),
    LedgerSeed(25, "Moneybird B.V.", "Bookkeeping software monthly subscription", 34.00, True, _SOFT),
    LedgerSeed(27, "Coolblue B.V.", "Monitor and keyboard", 389.00, False, _OFFICE),
    LedgerSeed(30, "NS Reizigers B.V.", "Train travel for client site visit", 27.60, True, _TRAVEL),
    LedgerSeed(33, "Albert Heijn", "Coffee and office snacks", 28.17, True, _OTHER),
    LedgerSeed(34, "Slack Technologies Inc", "Monthly team messaging subscription", 52.50, True, _SOFT),
    LedgerSeed(36, "KPN Zakelijk", "Monthly internet and phone service", 89.00, True, _UTIL),
    LedgerSeed(39, "Spaces Zuidas B.V.", "Monthly office rent payment", 1850.00, True, _RENT),
    LedgerSeed(40, "Jansen & De Wit Legal LLP", "Quarterly legal consultation retainer", 900.00, False, _PROF),
    LedgerSeed(43, "Eneco Zakelijk", "Electricity and gas usage", 198.12, True, _UTIL),
    LedgerSeed(44, "Bol.com Zakelijk", "Printer paper and toner cartridges", 118.40, True, _OFFICE),
    LedgerSeed(46, "Google Ireland Ltd", "Google Workspace monthly subscription", 69.00, True, _SOFT),
    LedgerSeed(47, "KLM Royal Dutch Airlines", "Flight for client site visit", 286.14, True, _TRAVEL),
    LedgerSeed(50, "Waternet", "Water usage", 86.40, False, _UTIL),
    LedgerSeed(55, "PostNL", "Postage and parcel shipping", 17.90, True, _OTHER),
    LedgerSeed(58, "NS Reizigers B.V.", "Train travel for client site visit", 58.80, True, _TRAVEL),
    LedgerSeed(63, "Action", "Miscellaneous business purchase", 14.25, True, _OTHER),
    LedgerSeed(66, "KPN Zakelijk", "Monthly internet and phone service", 89.00, True, _UTIL),
    LedgerSeed(69, "Spaces Zuidas B.V.", "Monthly office rent payment", 1850.00, True, _RENT),
    LedgerSeed(73, "Eneco Zakelijk", "Electricity and gas usage", 176.90, True, _UTIL),
    LedgerSeed(75, "Hema", "Coffee notebooks and pens", 23.85, True, _OFFICE),
    LedgerSeed(80, "Van Dijk Accounting", "Annual tax filing preparation", 1250.00, False, _PROF),
    LedgerSeed(85, "Kamer van Koophandel", "Trade register extract", 18.40, True, _OTHER),
)

# Items waiting in the review queue.
#
# HAND-SET, NOT MODEL OUTPUT: the first five carry an illustrative account and
# confidence. The shipped classifier is trained on a tiny synthetic set and
# does not clear the confidence gate on any of these (it does not on its own
# training rows either), so with real scores every item would be flagged and
# the bulk-confirm flow could not be shown at all. These numbers show what the
# queue looks like when the model IS confident; they are not a measurement of
# it. The demo banner says so on screen. Whether such an item needs review is
# still decided by the real gate (needs_manual_review), and its entry is built
# by the real rules layer.
#
# The last two are untouched real classifier output: an ambiguous marketplace
# order and an accountant's invoice, both of which the model is genuinely
# unsure about, so the escalation flow shown is the real one.
QUEUE_SEED: tuple[QueueSeed, ...] = (
    QueueSeed(1, "KPN Zakelijk", "Monthly internet and phone service", 89.00, True, _UTIL, 0.93),
    QueueSeed(1, "Slack Technologies Inc", "Monthly team messaging subscription", 52.50, True, _SOFT, 0.95),
    QueueSeed(2, "Spaces Zuidas B.V.", "Monthly office rent payment", 1850.00, False, _RENT, 0.91),
    QueueSeed(3, "NS Reizigers B.V.", "Train travel for client site visit", 36.40, True, _TRAVEL, 0.88),
    QueueSeed(4, "Office Centre", "Bulk copy paper order", 71.30, False, _OFFICE, 0.86),
    QueueSeed(2, "Bol.com", "Order 1183920411", 249.99, True),
    QueueSeed(5, "Van Dijk Accounting", "Quarterly VAT filing preparation", 425.00, False),
)


def _filename(vendor: str, day: date) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in vendor.lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"demo-{slug}-{day.isoformat()}.pdf"


def seed(classifier, serialize_entry: Callable, today: date | None = None) -> dict:
    """Write the demo history and review queue into the CURRENT user's
    directory. Refuses to run outside a per-user context, so it can never
    touch the legacy single-user files or the shared training data.

    `serialize_entry` is the web layer's JournalEntry -> dict serializer, the
    same one /api/process uses for the queue's entry_json cache."""
    if userdata.current_user_dir.get() is None:
        raise userdata.UserDataError("demo data can only be seeded into a user's own directory")
    today = today or date.today()
    now = datetime.now(timezone.utc)

    for item in LEDGER_SEED:
        day = today - timedelta(days=item.days_ago)
        proposal = propose_entry(item.vendor, item.description, item.amount, item.paid, day.isoformat(), classifier)
        construct_entry(item.account, item.amount, item.paid)  # balance invariant, raises RuleViolation
        was_corrected = proposal.predicted_account != item.account
        posted = datetime.combine(day, time(10, 0), tzinfo=timezone.utc)
        append_entry(
            filename=_filename(item.vendor, day),
            vendor=item.vendor,
            description=item.description,
            date=day.isoformat(),
            amount=item.amount,
            account=item.account,
            confidence=proposal.confidence,
            was_corrected=was_corrected,
            confirmed_at=min(posted, now).isoformat(timespec="seconds"),
        )
        if was_corrected:
            record_correction(
                vendor=item.vendor,
                description=item.description,
                predicted_account=proposal.predicted_account,
                corrected_account=item.account,
                amount=item.amount,
                date=day.isoformat(),
            )

    for item in QUEUE_SEED:
        day = today - timedelta(days=item.days_ago)
        proposal = propose_entry(item.vendor, item.description, item.amount, item.paid, day.isoformat(), classifier)
        account, confidence = proposal.predicted_account, proposal.confidence
        needs_review, entry, reason = proposal.needs_review, proposal.entry, proposal.rejection_reason
        if item.illustrative_confidence is not None:  # hand-set, see QUEUE_SEED
            account, confidence = item.illustrative_account, item.illustrative_confidence
            needs_review, reason = needs_manual_review(confidence), None
            entry = construct_entry(account, item.amount, item.paid)
        enqueue(
            filename=_filename(item.vendor, day),
            vendor=item.vendor,
            description=item.description,
            date=day.isoformat(),
            amount=item.amount,
            paid=item.paid,
            predicted_account=account,
            confidence=confidence,
            needs_review=needs_review,
            rejection_reason=reason,
            entry_json=json.dumps(serialize_entry(entry)),
        )

    return {"ledger": len(LEDGER_SEED), "queue": len(QUEUE_SEED)}


def wipe(user_id: str) -> None:
    """Empty one user's data directory. The path is built from the random
    user id alone (userdata.user_dir_for validates its shape)."""
    target = userdata.user_dir_for(user_id)
    if not target.is_dir() or target.is_symlink():
        return
    for child in target.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def reset(user_id: str, classifier, serialize_entry: Callable, today: date | None = None) -> dict:
    """Wipe and reseed a demo user's data, under that user's lock so an
    in-flight confirm in another tab can't interleave with it."""
    with userdata.lock_for(user_id), userdata.use_user_dir(userdata.user_dir_for(user_id, create=True)):
        wipe(user_id)
        return seed(classifier, serialize_entry, today)
