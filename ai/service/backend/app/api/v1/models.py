"""모델 레지스트리 제어 API(등록/활성화/롤백/메트릭)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from app.api.deps import get_state, require_api_key
from app.api.errors import api_error
from app.api.utils import ok_response
from app.schemas.model import ModelInfo
from app.services.model_runtime import (
    activate_model_runtime,
    deactivate_model_runtime,
    resolve_effective_engine,
)
from app.services.state import AppState

router = APIRouter(prefix="/v1", tags=["models"])


def _canonical_model_id(model_id: str) -> str:
    # 과거 모델 ID 별칭을 현재 표준 ID로 정규화한다.
    token = str(model_id or "").strip()
    if token == "ollama-paddleocr-vl":
        return "llamacpp-paddleocr-vl"
    if token == "ollama-glm-ocr":
        return "llamacpp-glm-ocr"
    return token


@router.get("/models", dependencies=[Depends(require_api_key)])
def list_models(request: Request, state: AppState = Depends(get_state)):
    # 상태 조회 전 런타임 엔진 가용 상태를 동기화한다.
    resolve_effective_engine(state, sync_registry=True)
    models = [model.model_dump() for model in state.model_registry.list_models()]
    return ok_response(request, models)


@router.post("/models/register", dependencies=[Depends(require_api_key)])
def register_model(model: ModelInfo, request: Request, state: AppState = Depends(get_state)):
    state.model_registry.register_model(model)
    return ok_response(request, {"registered": model.model_id})


@router.post("/models/{model_id}/activate", dependencies=[Depends(require_api_key)])
def activate_model(model_id: str, request: Request, state: AppState = Depends(get_state)):
    model_id = _canonical_model_id(model_id)
    try:
        # 레지스트리 active 전환 + 실제 엔진 warmup/바인딩까지 함께 수행한다.
        activated, runtime = activate_model_runtime(state, model_id)
    except KeyError as exc:
        raise api_error(status.HTTP_404_NOT_FOUND, "MODEL_NOT_FOUND", "Model not found") from exc
    except RuntimeError as exc:
        raise api_error(status.HTTP_409_CONFLICT, "MODEL_ACTIVATION_FAILED", str(exc)) from exc
    payload = activated.model_dump()
    payload.update(runtime)
    return ok_response(request, payload)


@router.post("/models/{model_id}/deactivate", dependencies=[Depends(require_api_key)])
def deactivate_model(model_id: str, request: Request, state: AppState = Depends(get_state)):
    model_id = _canonical_model_id(model_id)
    try:
        # 모델 비활성화와 함께 엔진 unload 결과를 runtime 필드로 반환한다.
        deactivated, runtime = deactivate_model_runtime(state, model_id)
    except KeyError as exc:
        raise api_error(status.HTTP_404_NOT_FOUND, "MODEL_NOT_FOUND", "Model not found") from exc
    payload = deactivated.model_dump()
    payload.update(runtime)
    return ok_response(request, payload)


@router.post("/models/{model_id}/rollback", dependencies=[Depends(require_api_key)])
def rollback_model(model_id: str, request: Request, state: AppState = Depends(get_state)):
    model_id = _canonical_model_id(model_id)
    try:
        # 지정 모델 기준 직전 버전을 찾아 롤백 후 즉시 활성화한다.
        target = state.model_registry.rollback(model_id)
        rolled_back, runtime = activate_model_runtime(state, target.model_id)
    except KeyError as exc:
        raise api_error(status.HTTP_404_NOT_FOUND, "MODEL_NOT_FOUND", "Model not found") from exc
    except RuntimeError as exc:
        raise api_error(status.HTTP_409_CONFLICT, "ROLLBACK_UNAVAILABLE", str(exc)) from exc
    payload = rolled_back.model_dump()
    payload.update(runtime)
    return ok_response(request, payload)


@router.post("/models/rollback", dependencies=[Depends(require_api_key)])
def rollback_latest(request: Request, state: AppState = Depends(get_state)):
    try:
        # 특정 모델 지정 없이 가장 최근 롤백 가능 대상을 적용한다.
        target = state.model_registry.rollback()
        rolled_back, runtime = activate_model_runtime(state, target.model_id)
    except RuntimeError as exc:
        raise api_error(status.HTTP_409_CONFLICT, "ROLLBACK_UNAVAILABLE", str(exc)) from exc
    payload = rolled_back.model_dump()
    payload.update(runtime)
    return ok_response(request, payload)


@router.get("/models/{model_id}/metrics", dependencies=[Depends(require_api_key)])
def model_metrics(model_id: str, request: Request, state: AppState = Depends(get_state)):
    model_id = _canonical_model_id(model_id)
    try:
        metrics = state.model_registry.get_metrics(model_id)
    except KeyError as exc:
        raise api_error(status.HTTP_404_NOT_FOUND, "MODEL_NOT_FOUND", "Model not found") from exc
    return ok_response(request, metrics.model_dump())
