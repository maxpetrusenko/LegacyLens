import json
from pathlib import Path

from legacylens.config import Settings
from legacylens.eval import run_precision_at_k_eval
from legacylens.models import RetrievalDiagnostics, RetrievalHit, RetrievalResult


def _build_eval_dataset(path: Path) -> None:
    rows = []
    for index in range(6):
        base = f"file_{index}.cob"
        rows.append(
            {
                "query": f"query-{index}",
                "relevant_files": [base],
                "relevant_citations": [f"[{base}:{line}-{line}]" for line in (10, 11, 12, 13)],
            }
        )
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_embedding_precision_gate_small_model(tmp_path: Path, monkeypatch) -> None:
    dataset_path = tmp_path / "eval.jsonl"
    _build_eval_dataset(dataset_path)

    def fake_retrieve(query, settings, codebase_path):
        row_index = int(query.split("-")[1])
        file_path = f"file_{row_index}.cob"
        hits = [
            RetrievalHit(file_path=file_path, line_start=line, line_end=line, text="line", score=0.9, metadata={})
            for line in (10, 11, 12, 13)
        ]
        hits.append(RetrievalHit(file_path="noise.cob", line_start=1, line_end=1, text="noise", score=0.1, metadata={}))
        return RetrievalResult(
            hits=hits,
            diagnostics=RetrievalDiagnostics(
                latency_ms=80,
                top1_score=0.9,
                chunks_returned=5,
                hybrid_triggered=False,
                semantic_hits=5,
                fallback_hits=0,
                confidence_level="high",
            ),
        )

    monkeypatch.setattr("legacylens.eval.retrieve_with_diagnostics", fake_retrieve)
    settings = Settings(openai_embed_model="text-embedding-3-small")
    result = run_precision_at_k_eval(dataset_path, tmp_path, settings, k=5)
    assert result["precision_at_k"] >= 0.70
