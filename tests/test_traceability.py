from pathlib import Path

from scripts.validate_traceability import validate_traceability


def test_traceability_matrix_validates() -> None:
    root = Path(__file__).resolve().parents[1]
    errors = validate_traceability(root / "docs" / "TRACEABILITY.md", root)
    assert not errors, "\n".join(errors)
