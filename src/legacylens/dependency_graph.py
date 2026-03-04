from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from legacylens.models import CodeChunk

Relation = Literal["perform", "call", "unknown"]


def normalize_called_symbol(raw_symbol: str) -> str | None:
    """Normalize symbol to uppercase name, returns None if invalid."""
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


def extract_relation(raw_symbol: str) -> Relation:
    """Extract relation type from raw symbol string."""
    if raw_symbol.startswith("PERFORM "):
        return "perform"
    if raw_symbol.startswith("CALL '") and raw_symbol.endswith("'"):
        return "call"
    return "unknown"


def build_callers_index(chunks: list[CodeChunk]) -> dict[str, list[str]]:
    callers_by_symbol: dict[str, set[str]] = defaultdict(set)
    for chunk in chunks:
        if not chunk.symbol_name:
            continue
        caller = chunk.symbol_name.upper()
        for raw_symbol in chunk.symbols_used:
            called_symbol = normalize_called_symbol(raw_symbol)
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


def build_edges_from_payloads(payloads: list[dict]) -> list[tuple[str, str]]:
    """Build edge list from payloads (legacy interface, returns typed edge tuples)."""
    return [e[:2] for e in build_typed_edges_from_payloads(payloads)]


def build_typed_edges_from_payloads(payloads: list[dict]) -> list[tuple[str, str, Relation]]:
    """Build typed edge list from payloads. Returns (source, target, relation) tuples."""
    edges: set[tuple[str, str, Relation]] = set()
    for payload in payloads:
        raw_caller = payload.get("symbol_name")
        if not isinstance(raw_caller, str) or not raw_caller:
            continue
        caller = raw_caller.upper()
        raw_used = payload.get("symbols_used", [])
        if not isinstance(raw_used, list):
            continue
        for raw_symbol in raw_used:
            callee = normalize_called_symbol(str(raw_symbol))
            if not callee:
                continue
            relation = extract_relation(str(raw_symbol))
            edges.add((caller, callee, relation))
    return sorted(edges)


def find_symbol_neighborhood(
    symbol_name: str, edges: list[tuple[str, str]], max_edges: int = 120
) -> tuple[list[str], list[tuple[str, str]]]:
    target = symbol_name.upper()
    if not target:
        return [], []
    incoming = [edge for edge in edges if edge[1] == target]
    outgoing = [edge for edge in edges if edge[0] == target]
    neighbors = {target}
    for source, _ in incoming:
        neighbors.add(source)
    for _, sink in outgoing:
        neighbors.add(sink)

    expanded = [edge for edge in edges if edge[0] in neighbors and edge[1] in neighbors]
    selected_edges = (incoming + outgoing + expanded)[:max_edges]
    selected_nodes = sorted({node for edge in selected_edges for node in edge} | {target})
    return selected_nodes, selected_edges


__all__ = [
    "build_callers_index",
    "build_edges_from_payloads",
    "build_typed_edges_from_payloads",
    "save_callers_index",
    "load_callers_index",
    "find_callers",
    "find_symbol_neighborhood",
    "normalize_called_symbol",
    "extract_relation",
    "Relation",
]
