from __future__ import annotations

import httpx

from legacylens.config import Settings
from legacylens.models import RetrievalHit
from legacylens.retrieval import format_citation


def _build_context(hits: list[RetrievalHit]) -> str:
    blocks: list[str] = []
    for hit in hits:
        citation = format_citation(hit.file_path, hit.line_start, hit.line_end)
        blocks.append(f"{citation}\n{hit.text}")
    return "\n\n".join(blocks)


def _fallback_answer(query: str, hits: list[RetrievalHit]) -> str:
    if not hits:
        return "No confident match found. Try a narrower query with symbol or file hints."
    lines = [f"Top matches for: {query}"]
    for hit in hits:
        citation = format_citation(hit.file_path, hit.line_start, hit.line_end)
        preview = hit.text.splitlines()[0][:160] if hit.text else ""
        lines.append(f"- {citation} {preview}")
    return "\n".join(lines)


def _openai_answer(settings: Settings, query: str, context: str) -> str:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")
    prompt = (
        "You are a COBOL codebase expert. Answer using ONLY the retrieved chunks below.\n\n"
        "Rules:\n"
        "- Always cite sources as: [file_path:line_start-line_end]\n"
        "- If context is insufficient, say exactly what is missing and suggest a follow-up query\n"
        "- Keep answers concise and developer-focused\n\n"
        f"Question: {query}\n\n"
        f"Retrieved context:\n{context}\n\n"
        "Answer:"
    )
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
        )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"]["content"].strip()


def generate_answer(
    query: str,
    hits: list[RetrievalHit],
    settings: Settings,
    *,
    confidence_level: str | None = None,
) -> str:
    context = _build_context(hits)
    if settings.llm_provider.lower() == "openai" and settings.openai_api_key:
        return _openai_answer(settings, query, context)
    answer = _fallback_answer(query, hits)
    if confidence_level == "low" and hits:
        return f"{answer}\n\nConfidence: low (verify against cited lines)."
    return answer


__all__ = ["generate_answer"]
