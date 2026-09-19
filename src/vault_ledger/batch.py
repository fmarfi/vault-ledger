"""Batch document processing -- run the pipeline over a list of documents.

Sequential for now, deliberately. Two real findings from this dev machine
drove that:

1. pypdfium2 (PDFium) is not thread-safe -- concurrent access from multiple
   threads in one process was reproduced to either hang or crash the whole
   process outright (SIGABRT), so a thread pool is out.
2. A process pool avoids that (separate processes, separate PDFium state)
   but this machine is memory-constrained (8GB RAM, observed under 200MB
   free during normal use) -- spawning extra worker processes, each
   loading its own full copy of scikit-learn/numpy/pandas, made the memory
   pressure worse, not better, and caused imports themselves to hang.

Revisit parallelism (most likely a process pool) once running on hardware
that isn't this tight on memory. Until then, sequential is correct, not
just simpler -- it doesn't fight the machine it runs on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vault_ledger.classifier.fusion_classifier import FusionClassifier
from vault_ledger.pipeline import PipelineResult, run_pipeline


@dataclass(frozen=True)
class BatchItemResult:
    document_path: Path
    result: PipelineResult | None
    error: str | None


def process_batch(
    document_paths: list[str | Path], classifier: FusionClassifier
) -> list[BatchItemResult]:
    """Runs run_pipeline() over every document, one at a time.

    A failure on one document (bad OCR, unparseable fields, a rules-layer
    rejection propagating as an unhandled error) never aborts the batch --
    it's captured per-item, the same principle the single-document web app
    already applies to one document at a time.
    """
    results = []
    for path in document_paths:
        path = Path(path)
        try:
            result = run_pipeline(path, classifier)
            results.append(BatchItemResult(document_path=path, result=result, error=None))
        except Exception as exc:  # noqa: BLE001 -- captured per-item, not swallowed
            results.append(BatchItemResult(document_path=path, result=None, error=str(exc)))
    return results
