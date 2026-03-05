#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

COBOL_EXTENSIONS = {".cob", ".cbl", ".cpy", ".cobol", ".at"}


def collect_corpus_metrics(codebase: Path) -> dict[str, int]:
    file_count = 0
    loc = 0
    for file_path in codebase.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in COBOL_EXTENSIONS:
            continue
        file_count += 1
        text = file_path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("*") or stripped.startswith("*>"):
                continue
            loc += 1
    return {"files": file_count, "loc": loc}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate COBOL corpus size targets.")
    parser.add_argument("--codebase", default="data", help="Path to codebase root.")
    parser.add_argument("--min-files", type=int, default=50, help="Minimum indexed file count.")
    parser.add_argument("--min-loc", type=int, default=10000, help="Minimum non-comment LOC.")
    args = parser.parse_args()

    metrics = collect_corpus_metrics(Path(args.codebase))
    metrics["min_files"] = args.min_files
    metrics["min_loc"] = args.min_loc
    metrics["ok"] = metrics["files"] >= args.min_files and metrics["loc"] >= args.min_loc
    print(json.dumps(metrics, indent=2))
    return 0 if metrics["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
