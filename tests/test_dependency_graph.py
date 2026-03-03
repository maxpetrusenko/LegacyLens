from pathlib import Path

from legacylens.dependency_graph import (
    build_callers_index,
    build_edges_from_payloads,
    find_callers,
    find_symbol_neighborhood,
    save_callers_index,
)
from legacylens.models import CodeChunk


def test_build_callers_index_and_lookup(tmp_path: Path) -> None:
    chunks = [
        CodeChunk(
            file_path="x.cob",
            line_start=1,
            line_end=10,
            text="",
            symbol_type="paragraph",
            symbol_name="MAIN",
            division="PROCEDURE DIVISION",
            section="ENTRY-SECTION",
            symbols_used=["PERFORM READ-FILE", "CALL 'LIBCALC'"],
            tags=[],
        ),
        CodeChunk(
            file_path="x.cob",
            line_start=11,
            line_end=20,
            text="",
            symbol_type="paragraph",
            symbol_name="WORKER",
            division="PROCEDURE DIVISION",
            section="ENTRY-SECTION",
            symbols_used=["PERFORM READ-FILE"],
            tags=[],
        ),
    ]
    callers = build_callers_index(chunks)
    assert callers["READ-FILE"] == ["MAIN", "WORKER"]
    assert callers["LIBCALC"] == ["MAIN"]

    graph_path = tmp_path / ".legacylens" / "dependency_graph.json"
    save_callers_index(graph_path, callers)
    assert find_callers("read-file", graph_path) == ["MAIN", "WORKER"]


def test_build_edges_and_neighborhood() -> None:
    payloads = [
        {"symbol_name": "main", "symbols_used": ["PERFORM READ-FILE", "CALL 'LIBCALC'"]},
        {"symbol_name": "worker", "symbols_used": ["PERFORM READ-FILE"]},
        {"symbol_name": "read-file", "symbols_used": ["CALL 'LIBCALC'"]},
    ]
    edges = build_edges_from_payloads(payloads)
    assert ("MAIN", "READ-FILE") in edges
    assert ("MAIN", "LIBCALC") in edges
    nodes, neighborhood_edges = find_symbol_neighborhood("read-file", edges)
    assert "READ-FILE" in nodes
    assert ("MAIN", "READ-FILE") in neighborhood_edges
