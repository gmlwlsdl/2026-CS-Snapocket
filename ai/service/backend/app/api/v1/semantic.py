"""이 파일은 백엔드가 호출하는 AI 검색 API를 제공한다.

- semantic search 실행
- 문서 벡터 upsert/delete/sync
- semantic search 가용성 상태 반환
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import get_state, require_api_key
from app.api.errors import api_error
from app.api.utils import ok_response
from app.services.semantic_search import SemanticDocument, SemanticSearchUnavailable
from app.services.state import AppState

router = APIRouter(prefix="/v1/search", tags=["semantic-search"])


class SemanticDocumentPayload(BaseModel):
    # 백엔드가 Qdrant 인덱싱을 위해 넘겨주는 최소 문서 단위 payload
    document_id: str
    user_id: str
    updated_at: str
    raw_text: str | None = None


class SemanticSearchRequest(BaseModel):
    # 검색 질의는 user_id 범위 안에서만 수행한다.
    query: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


class SemanticDeleteRequest(BaseModel):
    document_ids: list[str]
    user_id: str | None = None


class SemanticIndexStateRequest(BaseModel):
    user_id: str = Field(min_length=1)


class SemanticSyncRequest(BaseModel):
    user_id: str
    documents: list[SemanticDocumentPayload] = Field(default_factory=list)
    deleted_document_ids: list[str] = Field(default_factory=list)


def _service_or_503(state: AppState):
    # 앱 상태에 semantic search 서비스가 없으면 API 레벨에서 바로 503 처리한다.
    service = getattr(state, "semantic_search", None)
    if service is None:
        raise api_error(503, "SEMANTIC_SEARCH_UNAVAILABLE", "semantic search service is unavailable")
    return service


@router.get("/status", dependencies=[Depends(require_api_key)])
def semantic_status(request: Request, state: AppState = Depends(get_state)):
    # 모델 로딩, Qdrant 연결, 컬렉션 상태를 한 번에 확인할 수 있는 상태 API
    service = _service_or_503(state)
    return ok_response(request, service.availability_detail())


@router.post("/semantic", dependencies=[Depends(require_api_key)])
def semantic_search(request: Request, payload: SemanticSearchRequest, state: AppState = Depends(get_state)):
    service = _service_or_503(state)
    try:
        # 실제 유사도 검색은 서비스 계층에서 임베딩 생성 + Qdrant 조회로 처리한다.
        data = service.search(query=payload.query, user_id=payload.user_id, limit=payload.limit)
    except SemanticSearchUnavailable as exc:
        raise api_error(503, "SEMANTIC_SEARCH_UNAVAILABLE", str(exc)) from exc
    return ok_response(request, {"items": data})


@router.post("/index-state", dependencies=[Depends(require_api_key)])
def semantic_index_state(request: Request, payload: SemanticIndexStateRequest, state: AppState = Depends(get_state)):
    service = _service_or_503(state)
    try:
        data = service.list_documents(user_id=payload.user_id)
    except SemanticSearchUnavailable as exc:
        raise api_error(503, "SEMANTIC_SEARCH_UNAVAILABLE", str(exc)) from exc
    return ok_response(request, {"items": data})


@router.post("/upsert", dependencies=[Depends(require_api_key)])
def semantic_upsert(request: Request, payload: list[SemanticDocumentPayload], state: AppState = Depends(get_state)):
    service = _service_or_503(state)
    try:
        # 백엔드에서 넘긴 문서 목록을 SemanticDocument로 변환해 일괄 upsert한다.
        data = service.upsert_documents(
            [
                SemanticDocument(
                    document_id=item.document_id,
                    user_id=item.user_id,
                    updated_at=item.updated_at,
                    raw_text=item.raw_text or "",
                )
                for item in payload
            ]
        )
    except SemanticSearchUnavailable as exc:
        raise api_error(503, "SEMANTIC_SEARCH_UNAVAILABLE", str(exc)) from exc
    return ok_response(request, data)


@router.post("/delete", dependencies=[Depends(require_api_key)])
def semantic_delete(request: Request, payload: SemanticDeleteRequest, state: AppState = Depends(get_state)):
    service = _service_or_503(state)
    try:
        # 문서 삭제 또는 stale 정리 시 payload 기준으로 벡터를 제거한다.
        data = service.delete_documents(payload.document_ids, user_id=payload.user_id)
    except SemanticSearchUnavailable as exc:
        raise api_error(503, "SEMANTIC_SEARCH_UNAVAILABLE", str(exc)) from exc
    return ok_response(request, data)


@router.post("/sync", dependencies=[Depends(require_api_key)])
def semantic_sync(request: Request, payload: SemanticSyncRequest, state: AppState = Depends(get_state)):
    service = _service_or_503(state)
    try:
        # sync는 "유효 문서 upsert + 삭제 문서 제거"를 한 번에 처리하기 위한 엔드포인트다.
        data = service.sync_documents(
            documents=[
                SemanticDocument(
                    document_id=item.document_id,
                    user_id=item.user_id,
                    updated_at=item.updated_at,
                    raw_text=item.raw_text or "",
                )
                for item in payload.documents
            ],
            deleted_document_ids=payload.deleted_document_ids,
            user_id=payload.user_id,
        )
    except SemanticSearchUnavailable as exc:
        raise api_error(503, "SEMANTIC_SEARCH_UNAVAILABLE", str(exc)) from exc
    return ok_response(request, data)
