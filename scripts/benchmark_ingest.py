#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from legacylens.ingest import chunk_codebase, discover_cobol_files


def benchmark_ingest(codebase: Path) -> dict[str, object]:
    started = perf_counter()

    t0 = perf_counter()
    files = discover_cobol_files(codebase)
    discovery_sec = perf_counter() - t0

    t1 = perf_counter()
    chunks = chunk_codebase(codebase)
    chunking_sec = perf_counter() - t1

    # Runtime-only benchmark. External embedding/vector timings depend on provider credentials.
    embedding_sec = 0.0
    vector_insert_sec = 0.0
    total_sec = perf_counter() - started

    return {
        "files": len(files),
        "chunks": len(chunks),
        "duration_sec": round(total_sec, 3),
        "stages": {
            "discovery_sec": round(discovery_sec, 3),
            "chunking_sec": round(chunking_sec, 3),
            "embedding_sec": embedding_sec,
            "vector_insert_sec": vector_insert_sec,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark ingestion throughput.")
    parser.add_argument("--codebase", default="data", help="Path to codebase root.")
    args = parser.parse_args()
    result = benchmark_ingest(Path(args.codebase))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
