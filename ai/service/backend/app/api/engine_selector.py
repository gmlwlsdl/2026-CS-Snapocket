"""엔진 선택 공통 로직."""

from __future__ import annotations

from app.services.model_runtime import is_engine_active, resolve_effective_engine
from app.services.state import AppState


def normalize_engine_hint(engine_hint: str | None) -> str | None:
    if engine_hint is None:
        return None
    value = str(engine_hint).strip().lower()
    return value or None


def resolve_local_engine_hint(state: AppState, engine_hint: str | None) -> str:
    normalized = normalize_engine_hint(engine_hint)
    if normalized and normalized != "auto":
        if not is_engine_active(state, normalized):
            raise RuntimeError(
                f"Engine `{normalized}` is not active. Activate the model first from /ops/models."
            )
        if normalized == "paddle" and not state.router.paddle_engine.available():
            raise RuntimeError("Active Paddle model is unavailable")
        if normalized == "glm" and not state.router.glm_engine.available():
            raise RuntimeError("Active GLM model is unavailable")
        return normalized

    # 로컬 서버는 현재 활성 모델 상태를 단일 기준으로 강제한다.
    active_engine = resolve_effective_engine(state, sync_registry=True)
    if active_engine == "paddle" and state.router.paddle_engine.available():
        return "paddle"
    if active_engine == "glm" and state.router.glm_engine.available():
        return "glm"
    if active_engine in {"paddle", "glm"}:
        raise RuntimeError(f"Active model `{active_engine}` is unavailable")
    raise RuntimeError("No active model. Activate a model from /ops/models first.")
