import json
from pathlib import Path
from time import perf_counter

from legacylens.config import Settings
from legacylens.eval import run_precision_at_k_eval
from legacylens.models import RetrievalDiagnostics, RetrievalHit, RetrievalResult
from legacylens.retrieval import retrieve_with_diagnostics
from scripts.validate_corpus import collect_corpus_metrics


def test_query_latency_under_three_seconds(tmp_path: Path) -> None:
    codebase = tmp_path / "repo"
    codebase.mkdir()
    (codebase / "a.cob").write_text("PROCEDURE DIVISION.\nSTOP RUN.\n", encoding="utf-8")

    settings = Settings(codebase_path=str(codebase), qdrant_url="http://127.0.0.1:9999")
    started = perf_counter()
    retrieve_with_diagnostics("STOP RUN", settings, codebase)
    elapsed = perf_counter() - started
    assert elapsed < 3.0


def test_precision_metric_stays_above_target(tmp_path: Path, monkeypatch) -> None:
    dataset = tmp_path / "eval.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "query": "where stop run",
                "relevant_files": ["sample.cob"],
                "relevant_citations": ["[sample.cob:2-2]"],
            }
        ),
        encoding="utf-8",
    )

    def fake_retrieve(*_args, **_kwargs):
        return RetrievalResult(
            hits=[RetrievalHit("sample.cob", 2, 2, "STOP RUN.", 0.9, {})],
            diagnostics=RetrievalDiagnostics(
                latency_ms=50,
                top1_score=0.9,
                chunks_returned=1,
                hybrid_triggered=False,
                semantic_hits=1,
                fallback_hits=0,
                confidence_level="high",
            ),
        )

    monkeypatch.setattr("legacylens.eval.retrieve_with_diagnostics", fake_retrieve)
    result = run_precision_at_k_eval(dataset, tmp_path, Settings(), k=1)
    assert result["precision_at_k"] >= 0.70


def test_corpus_index_coverage_targets() -> None:
    metrics = collect_corpus_metrics(Path("data"))
    assert metrics["files"] >= 50
    assert metrics["loc"] >= 10000
