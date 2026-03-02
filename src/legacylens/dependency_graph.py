from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from legacylens.models import CodeChunk


def _normalize_called_symbol(raw_symbol: str) -> str | None:
    normalized: str | None = None
    if raw_symbol.startswith("PERFORM "):
        normalized = raw_symbol.removeprefix("PERFORM ").strip().upper()
    if raw_symbol.startswith("CALL '") and raw_symbol.endswith("'"):
        normalized = raw_symbol.removeprefix("CALL '").removesuffix("'").strip().upper()
    if normalized is None:
        return None
    if not any(char.isalpha() for char in normalized):
        return None
    return normalized


def build_callers_index(chunks: list[CodeChunk]) -> dict[str, list[str]]:
    callers_by_symbol: dict[str, set[str]] = defaultdict(set)
    for chunk in chunks:
        if not chunk.symbol_name:
            continue
        caller = chunk.symbol_name.upper()
        for raw_symbol in chunk.symbols_used:
            called_symbol = _normalize_called_symbol(raw_symbol)
            if not called_symbol:
                continue
            callers_by_symbol[called_symbol].add(caller)
    return {symbol: sorted(callers) for symbol, callers in callers_by_symbol.items()}


def save_callers_index(path: Path, callers_by_symbol: dict[str, list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "callers_by_symbol": callers_by_symbol,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_callers_index(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload.get("callers_by_symbol", {}))


def find_callers(symbol_name: str, graph_path: Path) -> list[str]:
    callers_by_symbol = load_callers_index(graph_path)
    return callers_by_symbol.get(symbol_name.upper(), [])


__all__ = [
    "build_callers_index",
    "save_callers_index",
    "load_callers_index",
    "find_callers",
]
