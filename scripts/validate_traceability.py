#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def _table_rows(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0] == "Req#":
            continue
        if len(cells) >= 6:
            rows.append(cells[:6])
    return rows


def _resolve_ref(root: Path, ref: str) -> Path | None:
    value = ref.strip().strip("`")
    if not value or value.startswith("http://") or value.startswith("https://"):
        return None
    direct = root / value
    if direct.exists():
        return direct
    docs_candidate = root / "docs" / value
    if docs_candidate.exists():
        return docs_candidate
    tests_candidate = root / "tests" / value
    if tests_candidate.exists():
        return tests_candidate
    return direct


def validate_traceability(doc_path: Path, root: Path) -> list[str]:
    errors: list[str] = []
    content = doc_path.read_text(encoding="utf-8")
    rows = _table_rows(content)
    if not rows:
        return ["Traceability table is missing rows."]

    for index, row in enumerate(rows, start=1):
        req, requirement, task, test_file, artifact_link, status = row
        if not req or not requirement or not task or not test_file or not artifact_link or not status:
            errors.append(f"Row {index}: empty required cell.")
            continue
        for label, ref in (("test", test_file), ("artifact", artifact_link)):
            resolved = _resolve_ref(root, ref)
            if resolved is not None and not resolved.exists():
                errors.append(f"Row {index}: missing {label} file {ref}.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate docs/TRACEABILITY.md integrity.")
    parser.add_argument("--doc", default="docs/TRACEABILITY.md", help="Traceability markdown path.")
    args = parser.parse_args()

    root = Path.cwd()
    doc_path = root / args.doc
    if not doc_path.exists():
        print(f"Missing file: {doc_path}")
        return 1

    errors = validate_traceability(doc_path, root)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Traceability OK: {args.doc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
