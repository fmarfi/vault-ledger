"""Editing a review-queue item before it is posted: /api/queue/<id>/preview,
/api/queue/<id>/update, confirm/correct with edited fields, the possible-
duplicate warning, and decided_by. Same fixture style as test_webapp_api.py.

The shared classifier is replaced by a small fake so the suggestion for a
given text is known; it still goes through pipeline.propose_entry and
construct_entry like the real one.
"""

import csv
import json

import pytest

from vault_ledger.userdata import use_user_dir
from vault_ledger.webapp import app as app_mod

from tests.helpers import make_user_client


class FakeCascade:
    """Rent for anything that mentions rent, utilities for power, else office
    supplies. `decide` is the cascade's interface (classifier/cascade.py)."""

    calls = 0

    def decide(self, vendor, description, amount=None, paid=None, date=None):
        FakeCascade.calls += 1
        text = f"{vendor} {description}".lower()
        if "rent" in text:
            return "Rent Expense", 0.91, "fake-model"
        if "power" in text:
            return "Utilities Expense", 0.42, "fake-model"
        return "Office Supplies Expense", 0.88, "fake-model"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_mod, "_classifier", FakeCascade())
    c = make_user_client(app_mod.app, "editor")
    c.pending_path = c.user_dir / "pending_queue.csv"
    c.ledger_path = c.user_dir / "ledger.csv"
    c.corrections_path = c.user_dir / "corrections.csv"
    return c


def _add(client, **overrides):
    fields = dict(
        filename="a.png",
        vendor="Acme Offce Suplies",  # OCR got it wrong
        description="Printer paper",
        date="2026-03-14",
        amount=100.0,
        paid=True,
        predicted_account="Office Supplies Expense",
        confidence=0.9,
        needs_review=False,
        rejection_reason=None,
        entry_json="{}",
    )
    fields.update(overrides)
    with use_user_dir(client.user_dir):
        return app_mod.enqueue(**fields)


def _rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


EDITED = {"vendor": "Main Street Properties", "description": "Office rent March", "date": "2026-03-01",
          "amount": 1250.5, "paid": False}


# ---- preview ------------------------------------------------------------------

def test_preview_reruns_the_proposal_and_changes_nothing(client):
    item_id = _add(client)
    before = client.pending_path.read_text()
    res = client.post(f"/api/queue/{item_id}/preview", json=EDITED)
    assert res.status_code == 200
    body = res.get_json()
    assert body["predicted_account"] == body["account"] == "Rent Expense"
    assert body["confidence"] == 0.91 and body["decided_by"] == "fake-model"
    assert body["needs_review"] is False
    # unpaid -> credit Accounts Payable, balanced, built by the rules
    assert body["entry"]["lines"] == [
        {"account": "Rent Expense", "debit": 1250.5, "credit": 0.0},
        {"account": "Accounts Payable", "debit": 0.0, "credit": 1250.5},
    ]
    assert body["entry"]["total_debits"] == body["entry"]["total_credits"] == 1250.5
    assert client.pending_path.read_text() == before
    assert not client.ledger_path.exists()


def test_preview_uses_the_reviewers_account_when_active(client):
    item_id = _add(client)
    body = client.post(f"/api/queue/{item_id}/preview", json={**EDITED, "account": "Utilities Expense"}).get_json()
    assert body["predicted_account"] == "Rent Expense"  # still reported as the suggestion
    assert body["account"] == "Utilities Expense"
    assert body["entry"]["lines"][0]["account"] == "Utilities Expense"


def test_preview_ignores_an_inactive_account(client):
    item_id = _add(client)
    body = client.post(f"/api/queue/{item_id}/preview", json={**EDITED, "account": "Accounts Payable"}).get_json()
    assert body["account"] == "Rent Expense"


def test_preview_flags_low_confidence_for_review(client):
    item_id = _add(client)
    body = client.post(f"/api/queue/{item_id}/preview", json={"description": "power bill"}).get_json()
    assert body["predicted_account"] == "Utilities Expense" and body["needs_review"] is True


def test_preview_unknown_item_is_404(client):
    assert client.post("/api/queue/nope/preview", json=EDITED).status_code == 404


@pytest.mark.parametrize(
    "bad",
    [
        {"amount": 0},
        {"amount": -5},
        {"amount": 0.004},  # rounds to 0.00
        {"amount": "nan"},
        {"amount": "inf"},
        {"amount": "1.234,56"},
        {"amount": True},
        {"amount": None},
        {"amount": 10_000_000_000},
        {"date": "03/14/2026"},
        {"date": "2026-02-30"},
        {"date": "2026-3-1"},
        {"vendor": "   "},
        {"vendor": "x" * 201},
        {"description": "x" * 1001},
        {"paid": "True"},
    ],
)
def test_preview_and_update_reject_bad_fields(client, bad):
    item_id = _add(client)
    before = client.pending_path.read_text()
    for route in ("preview", "update"):
        res = client.post(f"/api/queue/{item_id}/{route}", json={**EDITED, **bad})
        assert res.status_code == 400, (route, bad)
        assert res.get_json()["error"]
    assert client.pending_path.read_text() == before


def test_empty_date_is_allowed(client):
    item_id = _add(client)
    assert client.post(f"/api/queue/{item_id}/preview", json={**EDITED, "date": ""}).status_code == 200


# ---- update (save draft) ------------------------------------------------------

def test_update_rewrites_the_row_and_keeps_it_pending(client):
    item_id = _add(client)
    other = _add(client, vendor="Someone else", amount=7.0)
    res = client.post(f"/api/queue/{item_id}/update", json=EDITED)
    assert res.status_code == 200
    queue = {row["id"]: row for row in client.get("/api/queue").get_json()}
    row = queue[item_id]
    assert row["vendor"] == "Main Street Properties"
    assert row["description"] == "Office rent March"
    assert row["date"] == "2026-03-01"
    assert float(row["amount"]) == 1250.5
    assert row["paid"] == "False"
    assert row["predicted_account"] == "Rent Expense"
    assert float(row["confidence"]) == 0.91
    assert row["needs_review"] == "False" and row["rejection_reason"] == ""
    assert row["decided_by"] == "fake-model"
    assert json.loads(row["entry_json"])["lines"][1]["account"] == "Accounts Payable"
    assert row["filename"] == "a.png"
    assert queue[other]["vendor"] == "Someone else"  # the other row is untouched
    assert not client.ledger_path.exists()


def test_update_keeps_a_field_that_was_not_sent(client):
    item_id = _add(client, date="14 maart 2026")
    client.post(f"/api/queue/{item_id}/update", json={"vendor": "Acme Office Supplies"})
    row = client.get("/api/queue").get_json()[0]
    # An older row with the date as written is read as YYYY-MM-DD.
    assert row["date"] == "2026-03-14" and row["date_written"] == "14 maart 2026"
    assert row["vendor"] == "Acme Office Supplies"


def test_update_keeps_an_unchecked_assumed_date_flagged(client):
    item_id = _add(client, date="2026-04-03", date_written="03/04/2026", date_assumed=True, needs_review=True)
    client.post(f"/api/queue/{item_id}/update", json={"vendor": "Main Street Properties", "description": "rent"})
    row = client.get("/api/queue").get_json()[0]
    assert row["date_assumed"] == "True" and row["needs_review"] == "True"


def test_sending_the_date_settles_an_assumed_order(client):
    item_id = _add(client, date="2026-04-03", date_written="03/04/2026", date_assumed=True, needs_review=True)
    client.post(f"/api/queue/{item_id}/update", json={"date": "2026-03-04", "description": "rent"})
    row = client.get("/api/queue").get_json()[0]
    assert (row["date"], row["date_written"]) == ("2026-03-04", "03/04/2026")
    assert row["date_assumed"] == "" and row["needs_review"] == "False"


def test_preferences_route_reads_validates_and_saves(client):
    assert client.get("/api/preferences").get_json() == {"date_order": "day_first"}
    assert client.post("/api/preferences", json={"date_order": "sideways"}).status_code == 400
    assert client.post("/api/preferences", json={"date_order": "month_first"}).get_json() == {"date_order": "month_first"}
    assert client.get("/api/preferences").get_json() == {"date_order": "month_first"}
    assert (client.user_dir / "preferences.json").exists()
    other = make_user_client(app_mod.app, "neighbour")
    assert other.get("/api/preferences").get_json() == {"date_order": "day_first"}


def test_update_unknown_item_is_404(client):
    assert client.post("/api/queue/nope/update", json=EDITED).status_code == 404


def test_preview_and_update_need_csrf(client):
    item_id = _add(client)
    token, client.csrf = client.csrf, None
    for route in ("preview", "update"):
        assert client.post(f"/api/queue/{item_id}/{route}", json=EDITED).status_code == 403
    client.csrf = token


def test_other_user_cannot_preview_or_update_my_item(client):
    item_id = _add(client)
    other = make_user_client(app_mod.app, "stranger")
    assert other.post(f"/api/queue/{item_id}/preview", json=EDITED).status_code == 404
    assert other.post(f"/api/queue/{item_id}/update", json=EDITED).status_code == 404
    assert client.get("/api/queue").get_json()[0]["vendor"] == "Acme Offce Suplies"


# ---- confirm / correct with edits -------------------------------------------

def test_confirm_with_edits_posts_the_edited_fields(client):
    item_id = _add(client)
    res = client.post("/api/confirm", json={"id": item_id, **EDITED})
    assert res.status_code == 200
    entry = res.get_json()["entry"]
    assert entry["lines"][0] == {"account": "Rent Expense", "debit": 1250.5, "credit": 0.0}
    assert entry["lines"][1]["account"] == "Accounts Payable"
    [posted] = _rows(client.ledger_path)
    assert posted["vendor"] == "Main Street Properties"
    assert posted["description"] == "Office rent March"
    assert posted["date"] == "2026-03-01"
    assert float(posted["amount"]) == 1250.5
    assert posted["account"] == "Rent Expense"
    assert posted["was_corrected"] == "False"
    assert not client.corrections_path.exists()  # the model got the clean text right
    assert client.get("/api/queue").get_json() == []


def test_correct_with_edited_text_records_the_edited_text(client):
    item_id = _add(client)
    res = client.post("/api/correct", json={"id": item_id, "corrected_account": "Utilities Expense", **EDITED})
    assert res.status_code == 200
    [correction] = _rows(client.corrections_path)
    assert correction["vendor"] == "Main Street Properties"
    assert correction["description"] == "Office rent March"
    assert correction["predicted_account"] == "Rent Expense"  # the prediction on the clean text
    assert correction["corrected_account"] == "Utilities Expense"
    assert float(correction["amount"]) == 1250.5 and correction["date"] == "2026-03-01"
    [posted] = _rows(client.ledger_path)
    assert posted["account"] == "Utilities Expense" and posted["was_corrected"] == "True"


def test_correct_to_the_fresh_suggestion_is_not_a_correction(client):
    item_id = _add(client)
    client.post("/api/correct", json={"id": item_id, "corrected_account": "Rent Expense", **EDITED})
    assert not client.corrections_path.exists()
    assert _rows(client.ledger_path)[0]["was_corrected"] == "False"


def test_correct_without_edits_behaves_as_before(client):
    item_id = _add(client)
    client.post("/api/correct", json={"id": item_id, "corrected_account": "Utilities Expense"})
    [correction] = _rows(client.corrections_path)
    assert correction["vendor"] == "Acme Offce Suplies"
    assert correction["predicted_account"] == "Office Supplies Expense"
    calls = FakeCascade.calls
    other = _add(client, vendor="Second")
    client.post("/api/confirm", json={"id": other})
    assert FakeCascade.calls == calls  # nothing edited: no re-run


def test_amount_only_edit_changes_the_entry(client):
    item_id = _add(client)
    entry = client.post("/api/confirm", json={"id": item_id, "amount": "42.10", "paid": True}).get_json()["entry"]
    assert entry["total_debits"] == entry["total_credits"] == 42.1
    assert entry["lines"][1]["account"] == "Cash/Bank"


@pytest.mark.parametrize("route", ["/api/confirm", "/api/correct"])
def test_confirm_and_correct_reject_bad_edits_and_post_nothing(client, route):
    item_id = _add(client)
    body = {"id": item_id, "corrected_account": "Rent Expense", "amount": -1}
    res = client.post(route, json=body)
    assert res.status_code == 400
    assert not client.ledger_path.exists() and not client.corrections_path.exists()
    assert len(client.get("/api/queue").get_json()) == 1


def test_bulk_confirm_ignores_edited_fields(client):
    item_id = _add(client)
    res = client.post("/api/queue/bulk_confirm", json={"ids": [item_id], **EDITED}).get_json()
    assert res["confirmed"] == [item_id]
    assert _rows(client.ledger_path)[0]["vendor"] == "Acme Offce Suplies"


# ---- duplicates -------------------------------------------------------------

def test_queue_marks_a_copy_of_a_posted_document(client):
    posted = _add(client, filename="first.pdf")
    client.post("/api/confirm", json={"id": posted})
    again = _add(client, filename="again.pdf", vendor="  ACME offce suplies ")
    fresh = _add(client, filename="other.pdf", amount=55.0)
    queue = {row["id"]: row for row in client.get("/api/queue").get_json()}
    assert queue[again]["possible_duplicate"] is True
    assert queue[again]["duplicate_of"] == {"source": "ledger", "id": "", "filename": "first.pdf"}
    assert queue[fresh]["possible_duplicate"] is False and queue[fresh]["duplicate_of"] is None


def test_queue_marks_two_pending_copies(client):
    a = _add(client, filename="a.pdf")
    b = _add(client, filename="b.pdf")
    queue = {row["id"]: row for row in client.get("/api/queue").get_json()}
    assert queue[a]["duplicate_of"]["id"] == b and queue[b]["duplicate_of"]["id"] == a


def test_preview_reports_a_duplicate_of_the_edited_fields(client):
    posted = _add(client, filename="first.pdf", vendor="Main Street Properties", amount=1250.5, date="2026-03-01")
    client.post("/api/confirm", json={"id": posted})
    item_id = _add(client)
    body = client.post(f"/api/queue/{item_id}/preview", json=EDITED).get_json()
    assert body["possible_duplicate"] is True and body["duplicate_of"]["filename"] == "first.pdf"


def test_duplicate_never_blocks_a_single_post(client):
    a = _add(client, filename="a.pdf")
    _add(client, filename="b.pdf")
    assert client.post("/api/confirm", json={"id": a}).status_code == 200


def test_bulk_confirm_skips_possible_duplicates(client):
    fine = _add(client, filename="fine.pdf", vendor="Fine", amount=10.0)
    a = _add(client, filename="a.pdf")
    b = _add(client, filename="b.pdf")
    res = client.post("/api/queue/bulk_confirm", json={"ids": [fine, a, b]}).get_json()
    assert res["confirmed"] == [fine]
    failed = {f["id"]: f["error"] for f in res["failed"]}
    assert set(failed) == {a, b}
    assert "possible duplicate of b.pdf" in failed[a] and "individually" in failed[a]
    assert len(_rows(client.ledger_path)) == 1


def test_bulk_confirm_skips_a_copy_of_a_posted_document(client):
    first = _add(client, filename="first.pdf")
    client.post("/api/confirm", json={"id": first})
    again = _add(client, filename="again.pdf")
    res = client.post("/api/queue/bulk_confirm", json={"ids": [again]}).get_json()
    assert res["confirmed"] == []
    assert "already in the ledger" in res["failed"][0]["error"]


# ---- the page -----------------------------------------------------------------

def test_review_page_has_search_filters_and_multi_file_upload(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="queue-search"' in html
    for name in ("all", "review", "ready", "duplicate"):
        assert f'data-filter="{name}"' in html
    assert 'id="file-input"' in html and "multiple" in html.split('id="file-input"')[1].split(">")[0]
    assert "<script>" not in html  # no inline script blocks


# ---- decided_by -------------------------------------------------------------

def test_process_stores_decided_by(client, monkeypatch):
    # OCR is out of scope here: the extracted fields go straight to propose_entry.
    monkeypatch.setattr(
        app_mod, "run_pipeline",
        lambda path, classifier, date_order=None: app_mod.propose_entry("Acme", "Printer paper", 10.0, True, None, classifier),
    )
    res = client.post("/api/process", json={"sample": app_mod.SAMPLES[0].name})
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["decided_by"] == "fake-model"
    assert client.get("/api/queue").get_json()[0]["decided_by"] == "fake-model"


def test_old_queue_file_without_decided_by_still_loads_and_upgrades(client):
    client.pending_path.write_text(
        "id,queued_at,filename,vendor,description,date,amount,paid,predicted_account,"
        "confidence,needs_review,rejection_reason,entry_json\n"
        "old1,2026-01-01T00:00:00+00:00,old.png,Old Vendor,Old desc,,12.5,True,"
        "Office Supplies Expense,0.9,False,,{}\n"
    )
    [old] = client.get("/api/queue").get_json()
    # Loading the queue re-scores an item scored by an older model.
    assert old["id"] == "old1" and old["decided_by"] == "fake-model"
    new_id = _add(client, decided_by="fake-model")  # appending upgrades the header first
    rows = {row["id"]: row for row in _rows(client.pending_path)}
    assert rows["old1"]["decided_by"] == "fake-model" and rows["old1"]["vendor"] == "Old Vendor"
    assert rows[new_id]["decided_by"] == "fake-model" and rows[new_id]["vendor"] == "Acme Offce Suplies"
    assert client.post(f"/api/queue/old1/update", json={"vendor": "Renamed"}).status_code == 200
    assert client.post("/api/confirm", json={"id": "old1"}).status_code == 200


# ---- re-scoring stale items ---------------------------------------------------

def test_loading_the_queue_rescores_items_from_an_older_model_once(client):
    item_id = _add(client, vendor="Main Street Properties", description="Office rent", confidence=0.31,
                   predicted_account="Office Supplies Expense", needs_review=True, scored_with="1:old-model")
    row = client.get("/api/queue").get_json()[0]
    assert (row["predicted_account"], float(row["confidence"]), row["needs_review"]) == ("Rent Expense", 0.91, "False")
    assert row["scored_with"] == app_mod.scoring_version(app_mod._classifier)
    # The card and Edit details now agree.
    preview = client.post(f"/api/queue/{item_id}/preview", json={}).get_json()
    assert (preview["predicted_account"], preview["confidence"]) == ("Rent Expense", 0.91)
    calls = FakeCascade.calls
    client.get("/api/queue")
    assert FakeCascade.calls == calls  # current items are not scored again


def test_rescore_keeps_an_assumed_date_flagged(client):
    _add(client, vendor="Main Street Properties", description="Office rent", date="2026-04-03",
         date_written="03/04/2026", date_assumed=True, needs_review=True, scored_with="")
    row = client.get("/api/queue").get_json()[0]
    assert row["predicted_account"] == "Rent Expense" and row["needs_review"] == "True"


def test_page_gets_the_server_confidence_threshold(client):
    from vault_ledger.confidence_gate import CONFIDENCE_THRESHOLD
    page = client.get("/").get_data(as_text=True)
    assert f'<meta name="confidence-threshold" content="{CONFIDENCE_THRESHOLD}">' in page


# ---- documents page: the source document of a posted entry ----------------------

def _post_with_document(client, content=b"%PDF-1.4 fake", suffix=".pdf", filename="Factuur maart.pdf"):
    item_id = _add(client, filename=filename)
    folder = client.user_dir / "documents"
    folder.mkdir(exist_ok=True)
    (folder / f"{item_id}{suffix}").write_bytes(content)
    assert client.post("/api/confirm", json={"id": item_id}).status_code == 200
    return item_id


def test_confirm_links_the_ledger_entry_to_its_document(client):
    item_id = _post_with_document(client)
    [doc] = client.get("/api/documents").get_json()
    assert doc["document_id"] == item_id and doc["has_document"] is True


def test_original_downloads_as_an_attachment_under_its_own_name(client):
    item_id = _post_with_document(client)
    res = client.get(f"/api/documents/{item_id}/original")
    assert res.status_code == 200 and res.data == b"%PDF-1.4 fake"
    assert res.mimetype == "application/octet-stream"
    disposition = res.headers["Content-Disposition"]
    assert disposition.startswith("attachment") and "Factuur" in disposition


def test_preview_renders_an_image_document(client):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buf, "PNG")
    item_id = _post_with_document(client, content=buf.getvalue(), suffix=".png", filename="scan.png")
    res = client.get(f"/api/documents/{item_id}/preview")
    assert res.status_code == 200 and res.mimetype == "image/png"


def test_document_routes_are_per_user_and_reject_bad_ids(client):
    item_id = _post_with_document(client)
    other = make_user_client(app_mod.app, "outsider")
    for route in ("original", "preview"):
        assert other.get(f"/api/documents/{item_id}/{route}").status_code == 404
        assert client.get(f"/api/documents/..%2F..%2Fusers.json/{route}").status_code == 404
        assert client.get(f"/api/documents/000000000000/{route}").status_code == 404


def test_old_ledger_without_document_id_still_loads_and_upgrades(client):
    client.ledger_path.write_text(
        "confirmed_at,filename,vendor,description,date,amount,account,confidence,was_corrected\n"
        "2026-01-01T00:00:00+00:00,old.pdf,Old,desc,2026-01-01,5.0,Rent Expense,0.9,False\n"
    )
    [old] = client.get("/api/documents").get_json()
    assert old["document_id"] == "" and old["has_document"] is False
    _post_with_document(client)
    rows = _rows(client.ledger_path)
    assert len(rows) == 2 and rows[0]["vendor"] == "Old" and rows[0]["document_id"] == ""
