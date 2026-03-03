from pathlib import Path

from legacylens.config import Settings
from legacylens.structural import find_entry_point_hits


def test_find_entry_point_hits_scans_codebase_when_qdrant_unavailable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cob = repo / "main.cob"
    cob.write_text(
        "IDENTIFICATION DIVISION.\nPROGRAM-ID. MAINPROG.\nPROCEDURE DIVISION.\nSTOP RUN.\n",
        encoding="utf-8",
    )

    settings = Settings(codebase_path=str(repo), qdrant_url="http://127.0.0.1:9999")
    hits = find_entry_point_hits(settings, limit=3)

    assert len(hits) >= 1
    assert hits[0].file_path == "main.cob"
