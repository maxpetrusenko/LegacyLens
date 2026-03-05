from pathlib import Path

from scripts.benchmark_ingest import benchmark_ingest


def test_ingest_throughput_under_five_minutes() -> None:
    result = benchmark_ingest(Path("data"))
    assert result["duration_sec"] < 300
    assert result["files"] >= 50
    assert result["chunks"] > 0
    stages = result["stages"]
    assert "discovery_sec" in stages
    assert "chunking_sec" in stages
    assert "embedding_sec" in stages
    assert "vector_insert_sec" in stages
