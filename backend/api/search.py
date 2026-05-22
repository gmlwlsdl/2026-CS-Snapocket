from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from api.apiResponse import ApiResponse
from core.database import get_db
from core.security import jwtAuth
from models.document import Document
from models.document_tag import DocumentTag
from models.tag import Tag
from models.user import User
from services.semantic_search import (
    SemanticSearchError,
    ai_search_status,
    search_semantic_documents,
)

router = APIRouter(prefix="/search", tags=["search"])


class SearchItem(BaseModel):
    id: str
    title: str
    category: str
    summary: str
    tags: list[str]
    highlight: str
    score: float | None = None


class SearchResponse(BaseModel):
    items: list[SearchItem]


class SearchQueryResponse(BaseModel):
    mode_requested: str
    mode_used: str
    ai_available: bool
    items: list[SearchItem]


class SearchStatusResponse(BaseModel):
    ai_available: bool
    ai_live: bool
    reason: str


def _build_highlight(source: str, keyword: str, window: int = 32) -> str:
    if not source:
        return ""

    source_lower = source.lower()
    keyword_lower = keyword.lower()
    idx = source_lower.find(keyword_lower)

    if idx == -1:
        return source[:80]

    start = max(0, idx - window)
    end = min(len(source), idx + len(keyword) + window)
    snippet = source[start:end].strip()

    if start > 0:
        snippet = f"...{snippet}"
    if end < len(source):
        snippet = f"{snippet}..."

    return snippet


def _pick_highlight(doc: Document, tags: list[str], keyword: str) -> str:
    title = doc.title or ""
    summary = doc.summary or ""
    keyword_lower = keyword.lower()

    if keyword_lower in title.lower():
        return _build_highlight(title, keyword)

    if keyword_lower in summary.lower():
        return _build_highlight(summary, keyword)

    for tag in tags:
        if keyword_lower in tag.lower():
            return _build_highlight(f"#{tag}", keyword)

    return _build_highlight(summary or title, keyword)


def _require_user(jwt_token: dict, db: Session) -> User:
    user_email = jwt_token.get("sub")
    user_info = db.query(User).filter(User.email == user_email).first()
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "인증 정보를 확인할 수 없습니다.",
                "error_code": "UNAUTHORIZED",
            },
        )
    return user_info


def _load_tags_by_doc(db: Session, doc_ids: list[str]) -> dict[str, list[str]]:
    if not doc_ids:
        return {}
    tag_rows = (
        db.query(DocumentTag.document_id, Tag.name)
        .join(Tag, DocumentTag.tag_id == Tag.id)
        .filter(DocumentTag.document_id.in_(doc_ids))
        .all()
    )
    tags_by_doc: dict[str, list[str]] = defaultdict(list)
    for document_id, tag_name in tag_rows:
        tags_by_doc[str(document_id)].append(tag_name)
    return tags_by_doc


def _normalize_scores(items: list[tuple[str, float]]) -> dict[str, float]:
    if not items:
        return {}
    scores = [score for _doc_id, score in items]
    max_score = max(scores)
    min_score = min(scores)
    if max_score == min_score:
        return {doc_id: 1.0 for doc_id, _score in items}
    return {
        doc_id: round((score - min_score) / (max_score - min_score), 4)
        for doc_id, score in items
    }


def _text_score(doc: Document, tags: list[str], keyword: str) -> float:
    token = keyword.lower()
    title = (doc.title or "").lower()
    summary = (doc.summary or "").lower()
    category = (doc.category or "").lower()
    lowered_tags = [tag.lower() for tag in tags]
    score = 0.0

    if token in title:
        score = max(score, 1.0)
    if token in summary:
        score = max(score, 0.72)
    if token in category:
        score = max(score, 0.55)
    if any(token in tag for tag in lowered_tags):
        score = max(score, 0.86)

    query_tokens = [item for item in token.split() if item]
    if query_tokens:
        haystacks = [title, summary, category, " ".join(lowered_tags)]
        matched = 0
        for query_token in query_tokens:
            if any(query_token in haystack for haystack in haystacks):
                matched += 1
        if matched:
            score = max(score, min(0.98, 0.3 + (matched / len(query_tokens)) * 0.6))
    return round(score, 4)


def _text_search_documents(
    *,
    db: Session,
    user_id: str,
    keyword: str,
    category: str | None = None,
) -> list[tuple[Document, list[str], float]]:
    like_query = f"%{keyword}%"
    documents = (
        db.query(Document)
        .options(joinedload(Document.tag_objects))
        .filter(
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
            or_(
                Document.title.ilike(like_query),
                Document.summary.ilike(like_query),
                Document.category.ilike(like_query),
                Document.tag_objects.any(Tag.name.ilike(like_query)),
            ),
        )
        .all()
    )

    ranked: list[tuple[Document, list[str], float]] = []
    for doc in documents:
        if category and doc.category != category:
            continue
        tags = list(doc.tags)
        score = _text_score(doc, tags, keyword)
        ranked.append((doc, tags, score))

    ranked.sort(
        key=lambda item: (
            item[2],
            item[0].created_at or datetime.min,
        ),
        reverse=True,
    )
    return ranked


def _build_search_items(
    rows: list[tuple[Document, list[str], float]],
    *,
    keyword: str,
    offset: int = 0,
    limit: int | None = None,
) -> list[SearchItem]:
    sliced = rows[offset:] if limit is None else rows[offset : offset + limit]
    return [
        SearchItem(
            id=str(doc.id),
            title=doc.title or "",
            category=doc.category or "",
            summary=doc.summary or "",
            tags=tags,
            highlight=_pick_highlight(doc, tags, keyword),
            score=score,
        )
        for doc, tags, score in sliced
    ]


def _semantic_search(
    *,
    db: Session,
    user_id: str,
    keyword: str,
    category: str | None = None,
    limit: int = 20,
) -> list[SearchItem]:
    results = search_semantic_documents(query=keyword, user_id=user_id, limit=limit)
    if not results:
        return []

    result_ids = [str(item.get("document_id") or "") for item in results if str(item.get("document_id") or "").strip()]
    documents = (
        db.query(Document)
        .options(joinedload(Document.tag_objects))
        .filter(
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
            Document.id.in_(result_ids),
        )
        .all()
    )
    docs_by_id = {str(doc.id): doc for doc in documents}

    valid_rows: list[tuple[Document, list[str], float]] = []
    for item in results:
        doc_id = str(item.get("document_id") or "")
        doc = docs_by_id.get(doc_id)
        if doc is None:
            continue
        if category and doc.category != category:
            continue

        valid_rows.append((doc, list(doc.tags), float(item.get("score") or 0.0)))

    normalized = _normalize_scores([(str(doc.id), score) for doc, _tags, score in valid_rows])
    return [
        SearchItem(
            id=str(doc.id),
            title=doc.title or "",
            category=doc.category or "",
            summary=doc.summary or "",
            tags=tags,
            highlight=_pick_highlight(doc, tags, keyword),
            score=normalized.get(str(doc.id), 0.0),
        )
        for doc, tags, _score in valid_rows
    ]


@router.get("", response_model=ApiResponse[SearchResponse])
def search_documents(
    keyword: str = Query(..., description="검색어"),
    category: str | None = Query(None, description="카테고리 필터"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    jwt_token: dict = Depends(jwtAuth),
    db: Session = Depends(get_db),
):
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "검색어는 필수입니다.",
                "error_code": "KEYWORD_REQUIRED",
            },
        )

    user_info = _require_user(jwt_token, db)
    rows = _text_search_documents(
        db=db,
        user_id=str(user_info.id),
        keyword=normalized_keyword,
        category=category,
    )
    items = _build_search_items(
        rows,
        keyword=normalized_keyword,
        offset=(page - 1) * size,
        limit=size,
    )
    return ApiResponse(
        success=True,
        message="검색 결과 조회 성공",
        data=SearchResponse(items=items),
    )


@router.get("/status", response_model=ApiResponse[SearchStatusResponse])
def search_status():
    status_data = ai_search_status()

    return ApiResponse(
        success=True,
        message="검색 상태 조회 성공",
        data=SearchStatusResponse(
            ai_available=bool(status_data.get("available")),
            ai_live=bool(status_data.get("live")),
            reason=str(status_data.get("reason") or ""),
        ),
    )


@router.get("/query", response_model=ApiResponse[SearchQueryResponse])
def search_query(
    keyword: str = Query(..., description="검색어"),
    mode: str = Query("auto", pattern="^(auto|text|semantic)$"),
    category: str | None = Query(None, description="카테고리 필터"),
    size: int = Query(20, ge=1, le=100),
    jwt_token: dict = Depends(jwtAuth),
    db: Session = Depends(get_db),
):
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "검색어는 필수입니다.",
                "error_code": "KEYWORD_REQUIRED",
            },
        )

    user_info = _require_user(jwt_token, db)
    ai_status = ai_search_status()
    ai_available = bool(ai_status.get("available"))

    if mode in {"auto", "semantic"} and ai_available:
        try:
            items = _semantic_search(
                db=db,
                user_id=str(user_info.id),
                keyword=normalized_keyword,
                category=category,
                limit=size,
            )
            return ApiResponse(
                success=True,
                message="검색 결과 조회 성공",
                data=SearchQueryResponse(
                    mode_requested=mode,
                    mode_used="semantic",
                    ai_available=ai_available,
                    items=items,
                ),
            )
        except SemanticSearchError as exc:
            refreshed_status = ai_search_status(force_refresh=True)
            ai_available = bool(refreshed_status.get("available"))
            if mode == "semantic":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "success": False,
                        "message": str(exc),
                        "error_code": "SEMANTIC_SEARCH_UNAVAILABLE",
                    },
                ) from exc

    rows = _text_search_documents(
        db=db,
        user_id=str(user_info.id),
        keyword=normalized_keyword,
        category=category,
    )
    items = _build_search_items(rows, keyword=normalized_keyword, limit=size)
    return ApiResponse(
        success=True,
        message="검색 결과 조회 성공",
        data=SearchQueryResponse(
            mode_requested=mode,
            mode_used="text",
            ai_available=ai_available,
            items=items,
        ),
    )
