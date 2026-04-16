"""AI 추론 결과를 Snapocket 백엔드 문서 스키마로 매핑한다."""

from __future__ import annotations

from app.services.nlp.korean_extractor import KoreanExtractor

_extractor = KoreanExtractor()


def _normalize_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [token.strip() for token in value.split(",") if token.strip()]
    return []


def _derive_key_concepts(*, raw_text: str, summary: str, tags: list[str]) -> list[str]:
    if tags:
        return tags[:10]

    merged = " ".join([str(summary or "").strip(), str(raw_text or "").strip()]).strip()
    if not merged:
        return []

    nouns = _extractor.extract_nouns(merged)
    return [str(token).strip() for token in nouns if str(token).strip()][:10]


def map_to_backend_document_schema(payload: dict, *, fallback_doc_id: str | None = None) -> dict:
    data = payload if isinstance(payload, dict) else {}
    domain = data.get("domain") if isinstance(data.get("domain"), dict) else {}

    raw_text = (
        data.get("raw_text")
        or domain.get("raw_text")
        or data.get("corrected_text")
        or data.get("text")
        or ""
    )
    tags = _normalize_list(
        domain.get("tag")
        or domain.get("tags")
        or data.get("tags")
        or data.get("tag")
    )
    key_concepts = _normalize_list(data.get("key_concepts") or domain.get("key_concepts"))
    if not key_concepts:
        key_concepts = _derive_key_concepts(
            raw_text=str(raw_text),
            summary=str(domain.get("summary") or data.get("summary") or ""),
            tags=tags,
        )

    return {
        "doc_id": str(data.get("doc_id") or domain.get("req_id") or fallback_doc_id or ""),
        "title": str(domain.get("title") or data.get("title") or ""),
        "category": str(domain.get("category") or data.get("category") or "unknown"),
        "capture_date": data.get("capture_date") or domain.get("capture_date"),
        "summary": str(domain.get("summary") or data.get("summary") or ""),
        "tags": tags,
        "raw_text": str(raw_text),
        "key_concepts": key_concepts,
        "deadline": data.get("deadline") or domain.get("deadline"),
    }

