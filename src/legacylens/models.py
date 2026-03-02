from dataclasses import dataclass
import hashlib
from typing import Any


@dataclass(slots=True)
class CodeChunk:
    file_path: str
    line_start: int
    line_end: int
    text: str
    symbol_type: str
    symbol_name: str | None
    division: str | None
    section: str | None
    symbols_used: list[str]
    tags: list[str]
    language: str = "cobol"

    def point_id(self) -> int:
        raw = f"{self.file_path}:{self.line_start}:{self.line_end}".encode("utf-8")
        digest = hashlib.sha256(raw).digest()
        return int.from_bytes(digest[:8], "big", signed=False)

    def payload(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "symbol_type": self.symbol_type,
            "symbol_name": self.symbol_name,
            "division": self.division,
            "section": self.section,
            "symbols_used": self.symbols_used,
            "tags": self.tags,
            "language": self.language,
            "text": self.text,
        }


@dataclass(slots=True)
class RetrievalHit:
    file_path: str
    line_start: int
    line_end: int
    text: str
    score: float
    metadata: dict[str, Any]


@dataclass(slots=True)
class RetrievalDiagnostics:
    latency_ms: int
    top1_score: float
    chunks_returned: int
    hybrid_triggered: bool
    semantic_hits: int
    fallback_hits: int
    retrieval_error: str | None = None


@dataclass(slots=True)
class RetrievalResult:
    hits: list[RetrievalHit]
    diagnostics: RetrievalDiagnostics


__all__ = ["CodeChunk", "RetrievalHit", "RetrievalDiagnostics", "RetrievalResult"]
