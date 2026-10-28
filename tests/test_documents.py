"""Uploaded documents are kept per user and shown on the review card."""

import io

import pytest
from PIL import Image

from vault_ledger.pipeline import PipelineResult
from vault_ledger.rules.entry_rules import construct_entry
from vault_ledger.webapp import app as app_mod

from tests.helpers import make_user_client


@pytest.fixture
def client(monkeypatch):
    def fake_pipeline(_path, _classifier, _date_order=None):
        return PipelineResult(
            vendor="Acme Office Supplies Inc",
            description="Printer paper",
            date="2026-03-14",
            amount=184.32,
            paid=False,
            predicted_account="Office Supplies Expense",
            confidence=0.9,
            needs_review=False,
            rejection_reason=None,
            entry=construct_entry("Office Supplies Expense", 184.32, False),
        )

    monkeypatch.setattr(app_mod, "run_pipeline", fake_pipeline)
    monkeypatch.setattr(app_mod, "_get_classifier", lambda: None)
    return make_user_client(app_mod.app, "carol")


def _png_bytes(color="white"):
    out = io.BytesIO()
    Image.new("RGB", (120, 160), color).save(out, "PNG")
    return out.getvalue()


def _upload(client, data=None, name="scan.png"):
    res = client.post("/api/process", data={"document": (io.BytesIO(data or _png_bytes()), name)})
    assert res.status_code == 200, res.get_json()
    return res.get_json()["id"]


def test_upload_is_kept_and_served_as_png(client):
    item_id = _upload(client)
    assert [p.name for p in (client.user_dir / "documents").iterdir()] == [f"{item_id}.png"]
    res = client.get(f"/api/queue/{item_id}/document")
    assert res.status_code == 200
    assert res.mimetype == "image/png"
    assert Image.open(io.BytesIO(res.data)).size == (120, 160)


def test_pdf_upload_is_served_as_an_image(client):
    fpdf = pytest.importorskip("fpdf")
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=14)
    pdf.cell(0, 8, "Invoice")
    item_id = _upload(client, bytes(pdf.output()), "invoice.pdf")
    res = client.get(f"/api/queue/{item_id}/document")
    assert res.status_code == 200
    assert res.mimetype == "image/png"


def test_unreadable_upload_gives_404_not_the_raw_file(client):
    item_id = _upload(client, b"<script>alert(1)</script>", "page.html")
    res = client.get(f"/api/queue/{item_id}/document")
    assert res.status_code == 404
    assert b"script" not in res.data


def test_another_user_cannot_see_the_document(client):
    item_id = _upload(client)
    other = make_user_client(app_mod.app, "dave")
    assert other.get(f"/api/queue/{item_id}/document").status_code == 404
    assert not (other.user_dir / "documents").exists()


def test_dismiss_deletes_the_document_and_confirm_keeps_it(client):
    dismissed = _upload(client)
    kept = _upload(client)
    assert client.delete(f"/api/queue/{dismissed}").status_code == 200
    assert client.post("/api/confirm", json={"id": kept}).status_code == 200
    assert [p.stem for p in (client.user_dir / "documents").iterdir()] == [kept]
    # no longer pending, so the review route has nothing to show
    assert client.get(f"/api/queue/{kept}/document").status_code == 404


def test_sample_item_shows_the_sample_image(client):
    sample = app_mod.SAMPLES[0].name
    if not (app_mod.DOCUMENTS_DIR / f"{sample}.png").exists():
        pytest.skip("sample images not generated")
    item_id = client.post("/api/process", json={"sample": sample}).get_json()["id"]
    res = client.get(f"/api/queue/{item_id}/document")
    assert res.status_code == 200
    assert res.mimetype == "image/png"


def test_bad_item_id_is_404(client):
    assert client.get("/api/queue/..%2F..%2Fusers/document").status_code == 404
    assert client.get("/api/queue/zzzzzzzzzzzz/document").status_code == 404
