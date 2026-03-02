from __future__ import annotations

import re

from legacylens.models import CodeChunk

RESERVED_KEYWORDS = {
    "MOVE",
    "IF",
    "PERFORM",
    "OPEN",
    "READ",
    "WRITE",
    "CLOSE",
    "STOP",
    "EVALUATE",
    "ADD",
    "SUBTRACT",
    "MULTIPLY",
    "DIVIDE",
    "COMPUTE",
    "DISPLAY",
    "ACCEPT",
    "PROCEDURE",
    "DIVISION",
    "SECTION",
}

IO_PATTERN = re.compile(r"\b(OPEN|READ|WRITE|CLOSE|SELECT|FD)\b", re.IGNORECASE)
ERR_PATTERN = re.compile(r"\b(ON ERROR|INVALID KEY|AT END|NOT AT END|EXCEPTION)\b", re.IGNORECASE)
PERFORM_PATTERN = re.compile(r"\bPERFORM\s+([A-Z0-9-]+)\b", re.IGNORECASE)
CALL_PATTERN = re.compile(r"\bCALL\s+['\"]([A-Z0-9_-]+)['\"]", re.IGNORECASE)
DIVISION_PATTERN = re.compile(r"^\s*([A-Z-]+)\s+DIVISION\.\s*$", re.IGNORECASE)
SECTION_PATTERN = re.compile(r"^\s*([A-Z0-9-]+)\s+SECTION\.\s*$", re.IGNORECASE)
PARAGRAPH_PATTERN = re.compile(r"^\s*([A-Z0-9-]+(?:\s+[A-Z0-9-]+){0,3})\.\s*$", re.IGNORECASE)


def _is_valid_paragraph_label(label: str) -> bool:
    tokens = label.split()
    if not 1 <= len(tokens) <= 4:
        return False
    normalized = [token.upper() for token in tokens]
    if any(token in RESERVED_KEYWORDS for token in normalized):
        return False
    return all(re.fullmatch(r"[A-Z0-9-]+", token) is not None for token in normalized)


def _collect_chunk_tags(text: str, is_entry_candidate: bool) -> list[str]:
    tags: list[str] = []
    if IO_PATTERN.search(text):
        tags.append("io")
    if ERR_PATTERN.search(text):
        tags.append("error_handling")
    if is_entry_candidate:
        tags.append("entry_candidate")
    return tags


def _extract_symbols_used(text: str) -> list[str]:
    symbols: set[str] = set()
    for match in PERFORM_PATTERN.finditer(text):
        symbols.add(f"PERFORM {match.group(1).upper()}")
    for match in CALL_PATTERN.finditer(text):
        symbols.add(f"CALL '{match.group(1).upper()}'")
    return sorted(symbols)


def _fallback_chunks(file_path: str, lines: list[str], window: int = 80, overlap: int = 15) -> list[CodeChunk]:
    chunks: list[CodeChunk] = []
    step = max(1, window - overlap)
    for start_idx in range(0, len(lines), step):
        end_idx = min(len(lines), start_idx + window)
        chunk_lines = lines[start_idx:end_idx]
        if not chunk_lines:
            continue
        chunk_text = "\n".join(chunk_lines)
        chunks.append(
            CodeChunk(
                file_path=file_path,
                line_start=start_idx + 1,
                line_end=end_idx,
                text=chunk_text,
                symbol_type="fallback",
                symbol_name=None,
                division=None,
                section=None,
                symbols_used=_extract_symbols_used(chunk_text),
                tags=_collect_chunk_tags(chunk_text, is_entry_candidate="STOP RUN" in chunk_text.upper()),
            )
        )
        if end_idx >= len(lines):
            break
    return chunks


def chunk_cobol_file(file_path: str, content: str) -> list[CodeChunk]:
    lines = content.splitlines()
    if not lines:
        return []

    division_by_line: dict[int, str] = {}
    current_division: str | None = None
    in_procedure_division = False
    section_by_line: dict[int, str] = {}
    current_section: str | None = None
    paragraph_starts: list[tuple[int, str]] = []
    first_section_recorded = False
    first_section_name: str | None = None

    for idx, line in enumerate(lines, start=1):
        division_match = DIVISION_PATTERN.match(line)
        if division_match:
            current_division = f"{division_match.group(1).upper()} DIVISION"
            in_procedure_division = current_division == "PROCEDURE DIVISION"
            current_section = None

        division_by_line[idx] = current_division or ""

        if in_procedure_division:
            section_match = SECTION_PATTERN.match(line)
            if section_match:
                current_section = section_match.group(1).upper()
                if not first_section_recorded:
                    first_section_recorded = True
                    first_section_name = current_section
            section_by_line[idx] = current_section or ""

            paragraph_match = PARAGRAPH_PATTERN.match(line)
            if paragraph_match:
                label = paragraph_match.group(1).upper()
                if _is_valid_paragraph_label(label):
                    paragraph_starts.append((idx, label))

    if not paragraph_starts:
        return _fallback_chunks(file_path, lines)

    chunks: list[CodeChunk] = []
    for i, (start_line, symbol_name) in enumerate(paragraph_starts):
        end_line = paragraph_starts[i + 1][0] - 1 if i + 1 < len(paragraph_starts) else len(lines)
        if end_line < start_line:
            continue
        text = "\n".join(lines[start_line - 1 : end_line])
        division = division_by_line.get(start_line) or None
        section = section_by_line.get(start_line) or None
        is_entry_candidate = (section is not None and section == first_section_name) or "STOP RUN" in text.upper()
        chunks.append(
            CodeChunk(
                file_path=file_path,
                line_start=start_line,
                line_end=end_line,
                text=text,
                symbol_type="paragraph",
                symbol_name=symbol_name,
                division=division,
                section=section,
                symbols_used=_extract_symbols_used(text),
                tags=_collect_chunk_tags(text, is_entry_candidate=is_entry_candidate),
            )
        )

    return chunks


__all__ = ["chunk_cobol_file", "RESERVED_KEYWORDS"]
