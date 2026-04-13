"""시스템 상태 점검 API(live/ready/metrics/status)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from app.api.deps import get_state, require_api_key
from app.api.utils import ok_response
from app.services.dependency_checks import ping_redis
from app.services.model_runtime import resolve_effective_engine
from app.services.state import AppState

router = APIRouter(tags=["system"])


def _safe_engine_available(engine: object | None) -> bool:
    if engine is None or not hasattr(engine, "available"):
        return False
    try:
        return bool(engine.available())
    except Exception:
        return False


def _safe_engine_cache(engine: object | None) -> dict:
    if engine is None or not hasattr(engine, "availability_detail"):
        return {}
    try:
        detail = engine.availability_detail()
        return detail if isinstance(detail, dict) else {}
    except Exception:
        return {}


def _safe_qwen_asr_model(settings: object) -> str:
    return str(getattr(settings, "qwen_asr_model", "") or "").strip()


@router.get("/health/live")
def live():
    # 프로세스 생존 여부만 빠르게 확인하는 경량 엔드포인트.
    return {"ok": True}


@router.get("/health/ready")
def ready(state: AppState = Depends(get_state)):
    # readiness는 엔진 설정/런타임 + 핵심 인프라(DB/Redis) 상태를 종합 판단한다.
    resolve_effective_engine(state, sync_registry=True)
    qwen_asr_engine = getattr(state, "qwen_asr_engine", None)
    configured = {
        "paddle": state.settings.paddle_enable and bool(state.settings.llm_model_paddle),
        "qwen_asr": bool(state.settings.qwen_asr_enable) and bool(_safe_qwen_asr_model(state.settings)),
    }
    runtime = {
        "paddle": _safe_engine_available(state.router.paddle_engine),
        "qwen_asr": _safe_engine_available(qwen_asr_engine),
    }
    db = state.persistence.health(timeout_s=state.settings.readiness_timeout_s)
    redis = ping_redis(
        state.settings.redis_url if state.settings.redis_enable else None,
        timeout_s=state.settings.readiness_timeout_s,
    )
    dependencies = {
        "database": db,
        "redis": {
            "configured": redis.configured,
            "ok": redis.ok,
            "error": redis.error,
        },
    }

    # Ready 정책: OCR 설정이 존재하고, 핵심 인프라 의존성이 모두 정상이어야 한다.
    ready_ok = any(configured.values()) and db.get("ok", False) and redis.ok
    return {
        "ok": ready_ok,
        "configured": configured,
        "runtime": runtime,
        "dependencies": dependencies,
    }


@router.get("/metrics", response_class=PlainTextResponse)
def metrics(state: AppState = Depends(get_state)):
    # Prometheus scrape 포맷으로 내부 메트릭을 노출한다.
    return state.metrics.to_prometheus()


@router.get("/v1/system/status", dependencies=[Depends(require_api_key)])
def system_status(request: Request, state: AppState = Depends(get_state)):
    # 운영 화면/디버깅용으로 런타임 상태를 상세 스냅샷으로 제공한다.
    resolve_effective_engine(state, sync_registry=True)
    db = state.persistence.health(timeout_s=state.settings.readiness_timeout_s)
    redis = ping_redis(
        state.settings.redis_url if state.settings.redis_enable else None,
        timeout_s=state.settings.readiness_timeout_s,
    )
    qwen_asr_engine = getattr(state, "qwen_asr_engine", None)
    qwen_asr_model = _safe_qwen_asr_model(state.settings)
    llm_backend = {
        "base_url": state.settings.llm_base_url,
        "paddle_model": state.settings.llm_model_paddle,
        "request_timeout_s": state.settings.llm_request_timeout_s,
        "keep_alive": state.settings.llm_keep_alive,
        "temperature": state.settings.llm_temperature,
        "image_max_side_px": state.settings.llm_image_max_side_px,
        "max_tokens": state.settings.llm_max_tokens,
    }
    asr_backend = {
        "enabled": bool(state.settings.qwen_asr_enable),
        "model": qwen_asr_model,
        "language": str(state.settings.qwen_asr_language),
        "max_new_tokens": int(state.settings.qwen_asr_max_new_tokens),
    }
    data = {
        "queue": {
            "backend": state.settings.job_queue_backend,
        },
        "llm_backend": llm_backend,
        "asr_backend": asr_backend,
        "engines": {
            "paddle_available": _safe_engine_available(state.router.paddle_engine),
            "qwen_asr_available": _safe_engine_available(qwen_asr_engine),
            "paddle_cache": _safe_engine_cache(state.router.paddle_engine),
            "qwen_asr_cache": _safe_engine_cache(qwen_asr_engine),
        },
        "dependencies": {
            "database": db,
            "redis": {
                "configured": redis.configured,
                "ok": redis.ok,
                "error": redis.error,
            },
        },
        "models": [m.model_dump() for m in state.model_registry.list_models()],
        "jobs": [j.model_dump() for j in state.job_manager.list_jobs()],
        "metrics": state.metrics.snapshot(),
    }
    if state.dispatch is not None:
        active = state.dispatch.active_server()
        data["dispatch"] = {
            "active_server_id": active.server_id,
            "active_server_kind": str(getattr(active.kind, "value", active.kind)),
            "active_backend": state.dispatch.active_backend_label(),
        }
    return ok_response(request, data)
