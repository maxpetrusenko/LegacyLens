from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
from pathlib import Path

from legacylens.answer import generate_answer
from legacylens.config import Settings
from legacylens.dependency_graph import find_callers
from legacylens.eval import run_precision_at_k_eval
from legacylens.ingest import ingest_codebase
from legacylens.retrieval import format_citation, retrieve, retrieve_with_diagnostics


def run_ingest(codebase_path: str) -> None:
    settings = Settings(codebase_path=codebase_path)
    result = ingest_codebase(Path(codebase_path), settings)
    print(json.dumps(result, indent=2))


def run_query(query: str, codebase_path: str | None) -> None:
    settings = Settings(codebase_path=codebase_path or ".")
    retrieval = retrieve_with_diagnostics(query, settings, Path(settings.codebase_path))
    if retrieval.diagnostics.retrieval_error and not retrieval.hits:
        raise RuntimeError(
            "Retrieval failed: "
            f"{retrieval.diagnostics.retrieval_error}. "
            "Check embedding credentials, vector DB connectivity, and ingestion status."
        )
    hits = retrieval.hits
    if not hits:
        raise RuntimeError("No relevant context found. Refine query or ingest additional code.")
    answer = generate_answer(query, hits, settings)
    print(answer)
    print("\nSources:")
    for hit in hits:
        print(f"- {format_citation(hit.file_path, hit.line_start, hit.line_end)}")
    print("\nDiagnostics:")
    print(json.dumps(asdict(retrieval.diagnostics), indent=2))


def run_callers(symbol: str, codebase_path: str) -> None:
    settings = Settings(codebase_path=codebase_path)
    graph_path = Path(codebase_path) / settings.dependency_graph_file
    callers = find_callers(symbol, graph_path)
    payload = {"symbol": symbol.upper(), "callers": callers, "graph_path": str(graph_path)}
    print(json.dumps(payload, indent=2))


def run_eval(dataset_path: str, codebase_path: str, k: int, output_path: str | None) -> None:
    settings = Settings(codebase_path=codebase_path)
    result = run_precision_at_k_eval(
        dataset_path=Path(dataset_path),
        codebase_path=Path(codebase_path),
        settings=settings,
        k=k,
        output_path=Path(output_path) if output_path else None,
    )
    print(json.dumps(result, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LegacyLens MVP CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a COBOL codebase into Qdrant")
    ingest_parser.add_argument("--codebase", required=True, help="Path to COBOL codebase root")

    query_parser = subparsers.add_parser("query", help="Ask natural language questions")
    query_parser.add_argument("query", help="Question text")
    query_parser.add_argument("--codebase", default=".", help="Path to codebase for context expansion")

    callers_parser = subparsers.add_parser("callers", help="List who calls a COBOL symbol from dependency graph")
    callers_parser.add_argument("symbol", help="Target symbol name (e.g., READ-FILE)")
    callers_parser.add_argument("--codebase", required=True, help="Path to codebase root used for ingestion")

    eval_parser = subparsers.add_parser("eval", help="Run Precision@k evaluation from a labeled dataset")
    eval_parser.add_argument("--dataset", required=True, help="Path to JSONL eval dataset")
    eval_parser.add_argument("--codebase", required=True, help="Path to codebase root")
    eval_parser.add_argument("--k", type=int, default=5, help="Top-k for precision calculation")
    eval_parser.add_argument("--out", default=None, help="Optional output JSONL path for per-query logs")

    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "ingest":
            run_ingest(args.codebase)
            return

        if args.command == "query":
            run_query(args.query, args.codebase)
            return

        if args.command == "callers":
            run_callers(args.symbol, args.codebase)
            return

        if args.command == "eval":
            run_eval(args.dataset, args.codebase, args.k, args.out)
            return

        parser.error(f"Unknown command: {args.command}")
    except Exception as exc:
        parser.exit(status=2, message=f"Error: {exc}\n")


if __name__ == "__main__":
    main()
