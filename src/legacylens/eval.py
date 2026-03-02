from __future__ import annotations

import json
from pathlib import Path

from legacylens.config import Settings
from legacylens.retrieval import format_citation, retrieve_with_diagnostics


def _is_relevant(hit_citation: str, hit_file: str, row: dict) -> bool:
    relevant_citations = {item.strip() for item in row.get("relevant_citations", [])}
    relevant_files = {item.strip() for item in row.get("relevant_files", [])}
    return hit_citation in relevant_citations or hit_file in relevant_files


def run_precision_at_k_eval(
    dataset_path: Path,
    codebase_path: Path,
    settings: Settings,
    k: int = 5,
    output_path: Path | None = None,
) -> dict[str, float | int]:
    rows = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))

    if not rows:
        return {"queries": 0, "precision_at_k": 0.0}

    precision_scores: list[float] = []
    logs: list[dict[str, object]] = []
    for row in rows:
        query = str(row["query"])
        retrieval = retrieve_with_diagnostics(query, settings, codebase_path)
        hits = retrieval.hits[:k]
        relevant_count = 0
        for hit in hits:
            citation = format_citation(hit.file_path, hit.line_start, hit.line_end)
            if _is_relevant(citation, hit.file_path, row):
                relevant_count += 1
        precision = (relevant_count / k) if k else 0.0
        precision_scores.append(precision)
        logs.append(
            {
                "query": query,
                "precision_at_k": precision,
                "timestamp": row.get("timestamp"),
                "latency_ms": retrieval.diagnostics.latency_ms,
                "top1_score": retrieval.diagnostics.top1_score,
                "chunks_returned": retrieval.diagnostics.chunks_returned,
                "hybrid_triggered": retrieval.diagnostics.hybrid_triggered,
            }
        )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "\n".join(json.dumps(log, sort_keys=True) for log in logs) + "\n",
            encoding="utf-8",
        )

    average_precision = sum(precision_scores) / len(precision_scores)
    return {
        "queries": len(rows),
        "k": k,
        "precision_at_k": round(average_precision, 4),
    }


__all__ = ["run_precision_at_k_eval"]
