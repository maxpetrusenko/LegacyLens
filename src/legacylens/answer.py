from __future__ import annotations

import json
import re
from typing import Iterator

import httpx

from legacylens.config import Settings
from legacylens.models import RetrievalHit
from legacylens.observability import observe_model_call
from legacylens.retrieval import format_citation

_CITATION_PATTERN = re.compile(r"\[[^\[\]\n:]+:\d+-\d+\]")


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


def _build_answer_prompt(query: str, context: str) -> str:
    return (
        "You are a COBOL codebase expert. Use ONLY the retrieved context.\n\n"
        "Rules:\n"
        "- Cite factual claims with [file_path:line_start-line_end]\n"
        "- Include at least one citation in each explanatory paragraph\n"
        "- Explain behavior and control flow in detail (6-10 sentences)\n"
        "- Do not mention chunk counts, source counts, or 'retrieved context'\n"
        "- Do not invent actions or capabilities not shown in evidence\n"
        "- If evidence is insufficient, clearly state what is missing and suggest a follow-up query\n\n"
        f"Question: {query}\n\n"
        f"Retrieved context:\n{context}\n\n"
        "Answer:"
    )


def _openai_answer(settings: Settings, query: str, context: str, timeout: float) -> str:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")
    prompt = _build_answer_prompt(query, context)
    with observe_model_call(
        settings=settings,
        name="llm.openai.chat_completion",
        run_type="llm",
        provider="openai",
        model=settings.llm_model,
        input_count=1,
        inputs={
            "model": settings.llm_model,
            "query": query,
            "prompt": prompt,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        },
        metadata={"query_chars": len(query), "context_chars": len(context), "stream": False},
    ) as span:
        with httpx.Client(timeout=timeout) as client:
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
        answer = payload["choices"][0]["message"]["content"].strip()
        usage = payload.get("usage")
        span.set_outputs(
            {
                "answer": answer,
                "completion_chars": len(answer),
                "usage": usage if isinstance(usage, dict) else {},
            }
        )
        return answer


def _has_citation(answer: str) -> bool:
    return bool(_CITATION_PATTERN.search(answer or ""))


def _build_evidence_appendix(hits: list[RetrievalHit], limit: int = 5) -> str:
    if not hits:
        return ""
    lines: list[str] = ["Evidence:"]
    seen: set[str] = set()
    for hit in hits:
        citation = format_citation(hit.file_path, hit.line_start, hit.line_end)
        if citation in seen:
            continue
        seen.add(citation)
        preview = " ".join((hit.text or "").split())
        preview = preview[:160]
        lines.append(f"- {citation} {preview}".rstrip())
        if len(seen) >= limit:
            break
    return "\n".join(lines) if seen else ""


def _ensure_citations(answer: str, hits: list[RetrievalHit]) -> str:
    if not answer:
        return answer
    if _has_citation(answer):
        return answer
    appendix = _build_evidence_appendix(hits)
    if not appendix:
        return answer
    return f"{answer.rstrip()}\n\n{appendix}"


def generate_citations_only(hits: list[RetrievalHit]) -> str:
    if not hits:
        return ""
    lines = []
    for hit in hits:
        citation = format_citation(hit.file_path, hit.line_start, hit.line_end)
        lines.append(citation)
    return "\n".join(lines)


def _openai_stream_answer(settings: Settings, query: str, context: str) -> Iterator[dict[str, object]]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")
    prompt = _build_answer_prompt(query, context)
    usage: dict[str, int] | None = None
    finish_reason = "stop"
    token_chunks = 0
    completion_parts: list[str] = []
    with observe_model_call(
        settings=settings,
        name="llm.openai.chat_completion_stream",
        run_type="llm",
        provider="openai",
        model=settings.llm_model,
        input_count=1,
        inputs={
            "model": settings.llm_model,
            "query": query,
            "prompt": prompt,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "stream": True,
        },
        metadata={"query_chars": len(query), "context_chars": len(context), "stream": True},
    ) as span:
        with httpx.Client(timeout=settings.llm_timeout_sec) as client:
            with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    payload_raw = line[6:].strip()
                    if payload_raw == "[DONE]":
                        break
                    try:
                        payload = json.loads(payload_raw)
                    except json.JSONDecodeError:
                        continue

                    if isinstance(payload.get("usage"), dict):
                        usage = {
                            "prompt_tokens": int(payload["usage"].get("prompt_tokens", 0)),
                            "completion_tokens": int(payload["usage"].get("completion_tokens", 0)),
                            "total_tokens": int(payload["usage"].get("total_tokens", 0)),
                        }
                    choices = payload.get("choices", [])
                    if not choices:
                        continue
                    choice = choices[0]
                    if choice.get("finish_reason"):
                        finish_reason = str(choice.get("finish_reason"))
                    delta = choice.get("delta", {})
                    token = delta.get("content")
                    if token:
                        completion_parts.append(token)
                        token_chunks += 1
                        yield {"type": "token", "token": token}
        span.set_outputs(
            {
                "answer": "".join(completion_parts),
                "finish_reason": finish_reason,
                "token_chunks": token_chunks,
                "usage": usage or {},
            }
        )
    yield {"type": "done", "finish_reason": finish_reason, "usage": usage}


def stream_answer_tokens(
    query: str,
    hits: list[RetrievalHit],
    settings: Settings,
    *,
    confidence_level: str | None = None,
) -> Iterator[dict[str, object]]:
    if not hits:
        raise ValueError("No retrieval hits returned. Fix retrieval/config issues and retry the query.")
    if settings.llm_provider.lower() != "openai":
        raise ValueError("Unsupported LLM provider. Set LLM_PROVIDER=openai.")
    context = _build_context(hits)
    sources = [format_citation(hit.file_path, hit.line_start, hit.line_end) for hit in hits]
    answer_parts: list[str] = []
    usage: dict[str, int] | None = None
    with observe_model_call(
        settings=settings,
        name="synthesis.answer_stream",
        run_type="chain",
        provider="legacylens",
        model=settings.llm_model,
        input_count=1,
        inputs={
            "query": query,
            "confidence_level": confidence_level,
            "retrieved_context": context,
            "sources": sources,
        },
        metadata={"stream": True, "sources": len(sources)},
    ) as span:
        for event in _openai_stream_answer(settings, query, context):
            if event.get("type") == "token":
                answer_parts.append(str(event.get("token", "")))
            elif event.get("type") == "done":
                answer_text = "".join(answer_parts)
                if not _has_citation(answer_text):
                    appendix = _build_evidence_appendix(hits)
                    if appendix:
                        suffix = f"\n\n{appendix}"
                        answer_parts.append(suffix)
                        yield {"type": "token", "token": suffix}
                event_usage = event.get("usage")
                if isinstance(event_usage, dict):
                    usage = {k: int(v) for k, v in event_usage.items()}
            yield event
        span.set_outputs(
            {
                "answer": "".join(answer_parts),
                "usage": usage or {},
            }
        )


def generate_answer(
    query: str,
    hits: list[RetrievalHit],
    settings: Settings,
    *,
    confidence_level: str | None = None,
) -> str:
    if not hits:
        raise ValueError("No retrieval hits returned. Fix retrieval/config issues and retry the query.")

    context = _build_context(hits)
    if settings.llm_provider.lower() != "openai":
        raise ValueError("Unsupported LLM provider. Set LLM_PROVIDER=openai.")
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for answer generation.")
    sources = [format_citation(hit.file_path, hit.line_start, hit.line_end) for hit in hits]
    with observe_model_call(
        settings=settings,
        name="synthesis.answer",
        run_type="chain",
        provider="legacylens",
        model=settings.llm_model,
        input_count=1,
        inputs={
            "query": query,
            "confidence_level": confidence_level,
            "retrieved_context": context,
            "sources": sources,
        },
        metadata={"stream": False, "sources": len(sources)},
    ) as span:
        answer = _openai_answer(settings, query, context, settings.llm_timeout_sec)
        final_answer = _ensure_citations(answer, hits)
        if confidence_level == "low":
            final_answer = f"{final_answer}\n\nConfidence: low (verify against cited lines)."
        span.set_outputs({"answer": final_answer})
        return final_answer


__all__ = ["generate_answer", "generate_citations_only", "stream_answer_tokens"]
