"""엔진 선택 공통 로직."""

from __future__ import annotations

from app.services.state import AppState


def normalize_engine_hint(engine_hint: str | None) -> str | None:
    if engine_hint is None:
        return None
    value = str(engine_hint).strip().lower()
    if not value:
        return None
    if value in {"paddleocr", "paddle-ocr"}:
        return "paddle"
    if value in {"auto", "paddle", "qwen-asr"}:
        return value
    return "auto"


def resolve_local_engine_hint(state: AppState, engine_hint: str | None) -> str:
    normalized = normalize_engine_hint(engine_hint)
    # 로컬 OCR은 paddle 단일 엔진만 사용한다.
    if normalized and normalized not in {"auto", "paddle"}:
        raise RuntimeError("Local OCR engine is fixed to `paddle`.")
    if not state.router.paddle_engine.available():
        raise RuntimeError("Paddle OCR model is unavailable")
    return "paddle"
