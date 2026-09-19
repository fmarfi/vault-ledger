from pathlib import Path

from vault_ledger.batch import process_batch
from vault_ledger.classifier.fusion_classifier import FusionClassifier, load_training_data
from vault_ledger.synthetic_samples import SAMPLES

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "labeled_transactions.csv"
DOCUMENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "documents"


def _trained_classifier() -> FusionClassifier:
    df = load_training_data(DATA_PATH)
    classifier = FusionClassifier()
    classifier.fit(
        vendors=df["vendor"].tolist(),
        descriptions=df["description"].tolist(),
        accounts=df["account"].tolist(),
    )
    return classifier


def test_process_batch_preserves_order_and_matches_source_paths():
    classifier = _trained_classifier()
    paths = [DOCUMENTS_DIR / f"{s.name}_native.pdf" for s in SAMPLES]

    results = process_batch(paths, classifier)

    assert len(results) == len(paths)
    for path, item in zip(paths, results):
        assert item.document_path == path
        assert item.error is None
        assert item.result is not None
        assert item.result.entry is not None
        assert item.result.entry.total_debits == item.result.entry.total_credits


def test_process_batch_isolates_a_bad_document_from_the_rest():
    classifier = _trained_classifier()
    good_path = DOCUMENTS_DIR / f"{SAMPLES[0].name}_native.pdf"
    bad_path = Path("this/path/does/not/exist.png")

    results = process_batch([good_path, bad_path, good_path], classifier)

    assert results[0].error is None and results[0].result is not None
    assert results[1].error is not None and results[1].result is None
    assert results[2].error is None and results[2].result is not None
