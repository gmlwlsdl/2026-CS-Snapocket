"""디스패치 대상 서버(로컬/원격) 관리 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import get_state, require_api_key
from app.api.errors import api_error
from app.api.utils import ok_response
from app.schemas.server import ServerCreateRequest
from app.services.dispatch_service import DispatchRequestError
from app.services.server_registry import LOCAL_SERVER_ID
from app.services.state import AppState

router = APIRouter(prefix="/v1", tags=["servers"])


def _require_registry(state: AppState):
    # 서버 레지스트리/디스패치가 초기화되지 않았으면 즉시 실패시킨다.
    if state.server_registry is None or state.dispatch is None:
        raise RuntimeError("server registry is not initialized")
    return state.server_registry, state.dispatch


@router.get("/servers", dependencies=[Depends(require_api_key)])
def list_servers(request: Request, state: AppState = Depends(get_state)):
    registry, dispatch = _require_registry(state)
    # 서버 목록과 함께 현재 활성 서버의 큐 요약을 같이 제공한다.
    servers = [item.model_dump(mode="json") for item in registry.list_servers()]
    active_id = dispatch.active_server().server_id
    queue_summary = dispatch.active_queue_summary()
    return ok_response(
        request,
        {
            "servers": servers,
            "active_server_id": active_id,
            "active_queue_summary": queue_summary,
        },
    )


@router.get("/servers/active", dependencies=[Depends(require_api_key)])
def get_active_server(request: Request, state: AppState = Depends(get_state)):
    registry, dispatch = _require_registry(state)
    active = dispatch.active_server().model_dump(mode="json")
    queue_summary = dispatch.active_queue_summary()
    return ok_response(request, {"server": active, "queue_summary": queue_summary})


@router.post("/servers", dependencies=[Depends(require_api_key)])
def create_server(payload: ServerCreateRequest, request: Request, state: AppState = Depends(get_state)):
    registry, _dispatch = _require_registry(state)
    try:
        # 원격 서버 등록 시 URL/보안 정책 검증은 registry 계층에서 수행한다.
        created = registry.create_remote_server(payload)
    except ValueError as exc:
        raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_SERVER", str(exc)) from exc
    except RuntimeError as exc:
        raise api_error(status.HTTP_409_CONFLICT, "SERVER_CONFIG_ERROR", str(exc)) from exc
    return ok_response(request, created.model_dump(mode="json"))


@router.post("/servers/{server_id}/activate", dependencies=[Depends(require_api_key)])
def activate_server(server_id: str, request: Request, state: AppState = Depends(get_state)):
    registry, dispatch = _require_registry(state)
    try:
        # 활성 서버 전환 후, 즉시 새 활성 서버 기준 큐 현황을 반환한다.
        activated = registry.activate_server(server_id)
    except KeyError as exc:
        raise api_error(status.HTTP_404_NOT_FOUND, "SERVER_NOT_FOUND", "Server not found") from exc
    queue_summary = dispatch.active_queue_summary()
    return ok_response(request, {"server": activated.model_dump(mode="json"), "queue_summary": queue_summary})


@router.post("/servers/{server_id}/health-check", dependencies=[Depends(require_api_key)])
def health_check_server(server_id: str, request: Request, state: AppState = Depends(get_state)):
    _registry, dispatch = _require_registry(state)
    try:
        result = dispatch.health_check_server(server_id=server_id)
    except KeyError as exc:
        raise api_error(status.HTTP_404_NOT_FOUND, "SERVER_NOT_FOUND", "Server not found") from exc
    except DispatchRequestError as exc:
        raise api_error(exc.status_code, exc.code, exc.message) from exc
    return ok_response(request, result)


@router.delete("/servers/{server_id}", dependencies=[Depends(require_api_key)])
def delete_server(server_id: str, request: Request, state: AppState = Depends(get_state)):
    registry, dispatch = _require_registry(state)
    # 로컬 서버는 시스템 기본값이므로 삭제를 금지한다.
    if server_id == LOCAL_SERVER_ID:
        raise api_error(status.HTTP_409_CONFLICT, "SERVER_DELETE_FORBIDDEN", "Local server cannot be deleted")
    try:
        registry.delete_server(server_id)
    except KeyError as exc:
        raise api_error(status.HTTP_404_NOT_FOUND, "SERVER_NOT_FOUND", "Server not found") from exc
    active = dispatch.active_server().model_dump(mode="json")
    return ok_response(request, {"deleted": server_id, "active_server": active})
