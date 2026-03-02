from pathlib import Path

from legacylens.dependency_graph import build_callers_index, find_callers, save_callers_index
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
