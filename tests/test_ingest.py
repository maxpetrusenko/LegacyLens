from legacylens.ingest import summarize_chunks
from legacylens.models import CodeChunk


def test_summarize_chunks_includes_fallback_ratio() -> None:
    chunks = [
        CodeChunk("a.cob", 1, 2, "x", "paragraph", "MAIN", "PROCEDURE DIVISION", "MAIN-SECTION", [], []),
        CodeChunk("a.cob", 3, 4, "y", "fallback", None, None, None, [], []),
        CodeChunk("a.cob", 5, 6, "z", "fallback", None, None, None, [], []),
    ]
    summary = summarize_chunks(chunks)
    assert summary["total_chunks"] == 3
    assert summary["fallback_chunks"] == 2
    assert float(summary["fallback_ratio"]) == 2 / 3
