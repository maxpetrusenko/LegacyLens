from __future__ import annotations

from pathlib import Path

from legacylens.config import Settings
from legacylens.dependency_graph import normalize_called_symbol
from legacylens.models import RetrievalHit
from legacylens.vector_store import QdrantStore


def find_entry_point_hits(settings: Settings, limit: int = 5) -> list[RetrievalHit]:
    payloads: list[dict] = []
    try:
        store = QdrantStore(settings)
        payloads = store.iter_payloads()
    except Exception:
        payloads = []
    if not payloads:
        return _scan_codebase_for_entry_points(Path(settings.codebase_path), limit)
    called_symbols: set[str] = set()
    for payload in payloads:
        raw_used = payload.get("symbols_used", [])
        if not isinstance(raw_used, list):
            continue
        for raw_symbol in raw_used:
            normalized = normalize_called_symbol(str(raw_symbol))
            if normalized:
                called_symbols.add(normalized)

    hits: list[RetrievalHit] = []
    for payload in payloads:
        symbol_name = payload.get("symbol_name")
        if not isinstance(symbol_name, str) or not symbol_name:
            continue

        symbol_upper = symbol_name.upper()
        text = str(payload.get("text", ""))
        text_upper = text.upper()
        score = 0.0
        reasons: list[str] = []

        if symbol_upper not in called_symbols:
            score += 0.45
            reasons.append("no inbound calls")
        if "PROGRAM-ID" in text_upper:
            score += 0.25
            reasons.append("program-id declaration")
        if "STOP RUN" in text_upper or "GOBACK" in text_upper:
            score += 0.2
            reasons.append("termination verb")
        if any(token in symbol_upper for token in ("MAIN", "ENTRY", "START", "INIT")):
            score += 0.1
            reasons.append("entry-like symbol name")

        if score < 0.25:
            continue

        hits.append(
            RetrievalHit(
                file_path=str(payload.get("file_path", "")),
                line_start=int(payload.get("line_start", 1)),
                line_end=int(payload.get("line_end", 1)),
                text=text,
                score=min(score, 0.99),
                metadata={"source": "structural", "reasons": reasons, "symbol_name": symbol_name},
            )
        )

    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[:limit]


def _scan_codebase_for_entry_points(codebase_path: Path, limit: int) -> list[RetrievalHit]:
    patterns = {".cob", ".cbl", ".cpy", ".cobol"}
    hits: list[RetrievalHit] = []
    if not codebase_path.exists():
        return []
    for file_path in codebase_path.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in patterns:
            continue
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, start=1):
            upper = line.upper()
            score = 0.0
            reasons: list[str] = []
            if "PROGRAM-ID" in upper:
                score += 0.5
                reasons.append("program-id declaration")
            if "PROCEDURE DIVISION" in upper:
                score += 0.25
                reasons.append("procedure division")
            if "STOP RUN" in upper or "GOBACK" in upper:
                score += 0.25
                reasons.append("termination verb")
            if score <= 0:
                continue
            rel_path = str(file_path.relative_to(codebase_path))
            hits.append(
                RetrievalHit(
                    file_path=rel_path,
                    line_start=idx,
                    line_end=idx,
                    text=line.strip(),
                    score=min(score, 0.99),
                    metadata={"source": "structural_scan", "reasons": reasons},
                )
            )
            if len(hits) >= limit * 3:
                break
        if len(hits) >= limit * 3:
            break
    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[:limit]


__all__ = ["find_entry_point_hits"]
