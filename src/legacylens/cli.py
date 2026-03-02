from __future__ import annotations

import argparse
import json
from pathlib import Path

from legacylens.answer import generate_answer
from legacylens.config import Settings
from legacylens.ingest import ingest_codebase
from legacylens.retrieval import format_citation, retrieve


def run_ingest(codebase_path: str) -> None:
    settings = Settings(codebase_path=codebase_path)
    result = ingest_codebase(Path(codebase_path), settings)
    print(json.dumps(result, indent=2))


def run_query(query: str, codebase_path: str | None) -> None:
    settings = Settings(codebase_path=codebase_path or ".")
    hits = retrieve(query, settings, Path(settings.codebase_path))
    answer = generate_answer(query, hits, settings)
    print(answer)
    print("\nSources:")
    for hit in hits:
        print(f"- {format_citation(hit.file_path, hit.line_start, hit.line_end)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LegacyLens MVP CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a COBOL codebase into Qdrant")
    ingest_parser.add_argument("--codebase", required=True, help="Path to COBOL codebase root")

    query_parser = subparsers.add_parser("query", help="Ask natural language questions")
    query_parser.add_argument("query", help="Question text")
    query_parser.add_argument("--codebase", default=".", help="Path to codebase for context expansion")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        run_ingest(args.codebase)
        return

    if args.command == "query":
        run_query(args.query, args.codebase)
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
