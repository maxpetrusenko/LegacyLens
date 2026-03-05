from pathlib import Path
import os

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_core_requirement_artifacts_exist() -> None:
    required_files = [
        ROOT / "docs" / "ARCHITECTURE.md",
        ROOT / "docs" / "COST-ANALYSIS.md",
        ROOT / "docs" / "TRACEABILITY.md",
        ROOT / "docs" / "REQUIREMENTS-CHECKLIST.md",
        ROOT / "tests" / "test_embedding_precision.py",
        ROOT / "tests" / "test_fallback.py",
        ROOT / "tests" / "test_streaming.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_files if not path.exists()]
    assert not missing, f"Missing requirement artifacts: {missing}"


def test_requirements_checklist_has_nine_mvp_rows() -> None:
    checklist_path = ROOT / "docs" / "REQUIREMENTS-CHECKLIST.md"
    content = checklist_path.read_text(encoding="utf-8")
    mvp_rows = [line for line in content.splitlines() if line.startswith("| MVP-")]
    assert len(mvp_rows) >= 9


def test_optional_remote_health_check() -> None:
    deployed_url = os.getenv("LEGACYLENS_DEPLOYED_URL", "").strip()
    if not deployed_url:
        pytest.skip("LEGACYLENS_DEPLOYED_URL not set")
    response = httpx.get(f"{deployed_url.rstrip('/')}/health", timeout=5.0)
    assert response.status_code == 200
