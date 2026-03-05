from pathlib import Path

from scripts.validate_corpus import collect_corpus_metrics


def test_corpus_meets_minimum_size_targets() -> None:
    metrics = collect_corpus_metrics(Path("data"))
    assert metrics["files"] >= 50
    assert metrics["loc"] >= 10000
