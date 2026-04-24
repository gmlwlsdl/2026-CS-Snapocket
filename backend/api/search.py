from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.apiResponse import ApiResponse
from core.database import get_db
from core.security import jwtAuth
from models.document import Document
from models.document_tag import DocumentTag
from models.tag import Tag
from models.user import User

router = APIRouter(prefix="/search", tags=["search"])


class SearchItem(BaseModel):
    id: str
    title: str
    category: str
    summary: str
    tags: list[str]
    highlight: str


class SearchResponse(BaseModel):
    items: list[SearchItem]


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

    like_query = f"%{normalized_keyword}%"

    id_query = (
        db.query(Document.id, Document.created_at)
        .outerjoin(DocumentTag, Document.id == DocumentTag.document_id)
        .outerjoin(Tag, DocumentTag.tag_id == Tag.id)
        .filter(
            Document.user_id == user_info.id,
            Document.deleted_at.is_(None),
            or_(
                Document.title.ilike(like_query),
                Document.summary.ilike(like_query),
                Tag.name.ilike(like_query),
            ),
        )
    )

    if category:
        id_query = id_query.filter(Document.category == category)

    paged_rows = (
        id_query.group_by(Document.id, Document.created_at)
        .order_by(Document.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    doc_ids = [row[0] for row in paged_rows]

    if not doc_ids:
        return ApiResponse(
            success=True,
            message="검색 결과 조회 성공",
            data=SearchResponse(items=[]),
        )

    documents = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    docs_by_id = {doc.id: doc for doc in documents}

    tag_rows = (
        db.query(DocumentTag.document_id, Tag.name)
        .join(Tag, DocumentTag.tag_id == Tag.id)
        .filter(DocumentTag.document_id.in_(doc_ids))
        .all()
    )
    tags_by_doc: dict[str, list[str]] = defaultdict(list)
    for document_id, tag_name in tag_rows:
        tags_by_doc[document_id].append(tag_name)

    items: list[SearchItem] = []
    for doc_id in doc_ids:
        doc = docs_by_id.get(doc_id)
        if not doc:
            continue

        tags = tags_by_doc.get(doc.id, [])
        items.append(
            SearchItem(
                id=doc.id,
                title=doc.title or "",
                category=doc.category or "",
                summary=doc.summary or "",
                tags=tags,
                highlight=_pick_highlight(doc, tags, normalized_keyword),
            )
        )

    return ApiResponse(
        success=True,
        message="검색 결과 조회 성공",
        data=SearchResponse(items=items),
    )
