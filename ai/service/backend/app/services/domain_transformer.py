"""OCR 텍스트를 요청 처리 스키마(req_id/title/category/summary/raw_text/tag)로 정규화한다."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
import re
from typing import Any, Sequence

from app.schemas.infer import DomainPayload
from app.services.nlp.korean_extractor import KoreanExtractor, classify_doc_type_enhanced

_extractor = KoreanExtractor()

_DOC_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "notice": ("공지", "안내", "신청", "마감", "일정", "공고"),
    "lecture": ("강의", "수업", "과제", "시험", "출석", "교수", "학점"),
    "receipt": ("영수증", "합계", "총액", "결제", "승인", "카드"),
    "invoice": ("세금계산서", "청구서", "공급가액", "거래처", "사업자"),
    "contract": ("계약", "계약서", "갑", "을", "날인", "위약금"),
    "resume": ("이력서", "경력", "학력", "자기소개", "지원동기"),
    "form": ("신청서", "양식", "서식", "작성자", "신청인"),
    "report": ("보고서", "분석", "결론", "요약", "검토", "현황"),
}

_DOC_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "notice": ("notice", "공지", "공고", "안내"),
    "lecture": ("lecture", "강의", "수업"),
    "receipt": ("receipt", "영수증"),
    "invoice": ("invoice", "세금계산서", "청구서"),
    "contract": ("contract", "계약", "계약서"),
    "resume": ("resume", "이력서", "자기소개서"),
    "form": ("form", "신청서", "양식", "서식"),
    "report": ("report", "보고서", "리포트"),
}

_TAG_STOPWORDS: set[str] = {
    "합니다",
    "대한",
    "에서",
    "그리고",
    "또한",
    "관련",
    "기준",
    "내용",
    "첨부",
    "참고",
    "확인",
    "요청",
}


def _normalize_optional_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()

    token = str(value or "").strip()
    if not token:
        return None

    normalized = (
        token.replace("년", "-")
        .replace("월", "-")
        .replace("일", "")
        .replace(".", "-")
        .replace("/", "-")
    )
    match = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", normalized)
    if not match:
        return None
    year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _normalize_tags(value: Any, limit: int = 10) -> list[str]:
    if isinstance(value, str):
        raw_items = re.split(r"[,#\n]+", value)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        raw_items = [str(item) for item in value]
    else:
        raw_items = []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        tag = str(item or "").strip().lstrip("#").strip()
        if not tag:
            continue
        key = _normalize_token(tag)
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(tag[:40])
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_token(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").strip().lower())


def _split_tokens(value: str) -> list[str]:
    return [t for t in re.split(r"[\s_\-./:()\\[\]{}]+", str(value or "").lower()) if t.strip()]


def _title_from_hint_or_text(text: str, title_hint: str | None) -> str:
    hint = str(title_hint or "").strip()
    if hint:
        stem = Path(hint).stem.strip()
        if stem:
            return stem[:120]
        return hint[:120]
    for line in str(text or "").splitlines():
        token = line.strip()
        if token:
            return token[:120]
    return "untitled"


def _sentence_summary(text: str, limit: int = 3, max_chars: int = 300) -> str:
    sentences = [s.strip() for s in re.split(r"[\n.!?]+", str(text or "")) if s.strip()]
    if not sentences:
        return ""
    if len(sentences) <= limit:
        return " ".join(sentences)[:max_chars]

    nouns = _extractor.extract_nouns(text)
    weights = Counter(nouns)
    scored: list[tuple[int, int]] = []
    for idx, sentence in enumerate(sentences):
        score = sum(weights.get(token, 0) for token in _extractor.extract_nouns(sentence))
        scored.append((score, idx))
    top_indices = [idx for _score, idx in sorted(scored, key=lambda x: (x[0], -x[1]), reverse=True)[:limit]]
    ordered = [sentences[idx] for idx in sorted(top_indices)]
    return " ".join(ordered)[:max_chars]


def _extract_tags(text: str, limit: int = 10) -> list[str]:
    nouns = _extractor.extract_nouns(text)
    unique: list[str] = []
    seen: set[str] = set()
    for token in nouns:
        normalized = _normalize_token(token)
        if len(normalized) < 2:
            continue
        if normalized in _TAG_STOPWORDS:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(str(token).strip())
        if len(unique) >= limit:
            break
    return unique


def _resolve_doc_alias(category_name: str) -> str | None:
    normalized_name = _normalize_token(category_name)
    if not normalized_name:
        return None
    for alias_key, alias_tokens in _DOC_TYPE_ALIASES.items():
        for alias in alias_tokens:
            token = _normalize_token(alias)
            if token and token in normalized_name:
                return alias_key
    return None


def _category_score(text_lower: str, category_name: str, tags: list[str]) -> int:
    score = 0
    category_lower = str(category_name or "").strip().lower()
    if not category_lower:
        return score

    # 카테고리 문자열/토큰이 본문에 직접 등장하면 높은 점수를 부여한다.
    if category_lower in text_lower:
        score += text_lower.count(category_lower) * 4
    for token in _split_tokens(category_lower):
        if len(_normalize_token(token)) < 2:
            continue
        if token in text_lower:
            score += text_lower.count(token) * 2

    normalized_tags = {_normalize_token(tag) for tag in tags}
    if _normalize_token(category_name) in normalized_tags:
        score += 5

    alias = _resolve_doc_alias(category_name)
    if alias is not None:
        for keyword in _DOC_TYPE_KEYWORDS.get(alias, ()):
            k = keyword.lower()
            if k in text_lower:
                score += text_lower.count(k)

    return score


def _fallback_category(categories: list[str]) -> str:
    for token in categories:
        normalized = _normalize_token(token)
        if normalized in {"unknown", "uncategorized", "etc", "기타", "미분류"}:
            return token
    return categories[0] if categories else "unknown"


def _select_category(text: str, categories: Sequence[str], tags: list[str]) -> str:
    candidates = [str(c).strip() for c in categories if str(c).strip()]
    if not candidates:
        return "unknown"

    text_lower = str(text or "").lower()
    scored: list[tuple[int, str]] = []
    for category in candidates:
        scored.append((_category_score(text_lower, category, tags), category))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_category = scored[0]
    if best_score > 0:
        return best_category

    # 키워드 분류기가 예측한 문서 타입과 매핑 가능한 카테고리를 fallback으로 선택한다.
    predicted = classify_doc_type_enhanced(text)
    for category in candidates:
        if _resolve_doc_alias(category) == predicted:
            return category
    return _fallback_category(candidates)


def build_domain_payload(
    *,
    req_id: str,
    text: str,
    title_hint: str | None = None,
    categories: Sequence[str] | None = None,
) -> DomainPayload:
    cleaned_text = str(text or "").strip()
    tags = _extract_tags(cleaned_text)
    category = _select_category(cleaned_text, categories or [], tags)
    summary = _sentence_summary(cleaned_text, limit=3, max_chars=300) or "내용 없음"
    title = _title_from_hint_or_text(cleaned_text, title_hint)
    return DomainPayload(
        req_id=str(req_id or "").strip() or "unknown",
        title=title,
        category=category,
        summary=summary,
        raw_text=cleaned_text,
        tag=tags,
    )


def build_domain_payload_from_structured(
    *,
    req_id: str,
    payload: dict[str, Any] | None,
    fallback_text: str = "",
    title_hint: str | None = None,
    categories: Sequence[str] | None = None,
) -> DomainPayload:
    data = payload if isinstance(payload, dict) else {}
    raw_text = str(data.get("raw_text") or fallback_text or "").strip()
    fallback = build_domain_payload(
        req_id=req_id,
        text=raw_text,
        title_hint=title_hint,
        categories=categories,
    )
    allowed_categories = [str(c).strip() for c in (categories or []) if str(c).strip()]

    title = str(data.get("title") or "").strip()[:120] or fallback.title
    category = str(data.get("category") or "").strip() or fallback.category
    if allowed_categories and category not in allowed_categories:
        category = _select_category(raw_text, allowed_categories, fallback.tag)

    summary = str(data.get("summary") or "").strip()[:500] or fallback.summary
    tags = _normalize_tags(data.get("tags") or data.get("tag")) or fallback.tag

    return DomainPayload(
        req_id=str(req_id or "").strip() or "unknown",
        title=title,
        category=category,
        summary=summary,
        raw_text=raw_text,
        tag=tags,
        capture_date=_normalize_optional_date(data.get("capture_date")),
        deadline=_normalize_optional_date(data.get("deadline")),
    )
