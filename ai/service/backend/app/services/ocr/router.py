"""로컬 OCR 엔진 선택 라우터(paddle 단일 엔진)."""

from __future__ import annotations

from app.services.ocr.base import OCREngine


class OCREngineRouter:
    def __init__(
        self,
        paddle_engine: OCREngine,
        default_engine: str = "paddle",
        performance_provider=None,
    ) -> None:
        self.paddle_engine = paddle_engine
        self.default_engine = default_engine
        self.performance_provider = performance_provider

    def _resolve_hint(self, engine_hint: str | None) -> str:
        """요청 힌트가 없으면 기본 엔진 설정을 사용한다.

        현재 로컬 OCR은 `paddle` 단일 엔진만 지원한다.
        """
        if engine_hint:
            return str(engine_hint).strip().lower()
        return str(self.default_engine).strip().lower()

    @staticmethod
    def _unavailable_message(engine: OCREngine, label: str) -> str:
        detail = ""
        if hasattr(engine, "availability_detail"):
            try:
                info = engine.availability_detail()
                detail = str(info.get("last_error", "") or "").strip()
            except Exception:
                detail = ""
        return f"{label} profile unavailable" + (f": {detail}" if detail else "")

    def select(
        self,
        engine_hint: str | None,
        *,
        image_bytes: bytes | None = None,
        text_hint: str | None = None,
    ) -> OCREngine:
        """요청 힌트에 따라 paddle 엔진을 선택한다."""
        del image_bytes, text_hint
        hint = self._resolve_hint(engine_hint)
        if hint not in {"", "auto", "paddle"}:
            raise RuntimeError("Unsupported local OCR engine. Use `paddle`.")
        if self.paddle_engine.available():
            return self.paddle_engine
        raise RuntimeError(self._unavailable_message(self.paddle_engine, "PaddleOCR-VL"))

    def alternate(
        self,
        current_engine: str,
        *,
        image_bytes: bytes | None = None,
        text_hint: str | None = None,
    ) -> OCREngine | None:
        del current_engine, image_bytes, text_hint
        return None

    def select_with_fallback(
        self,
        *,
        primary_engine: str,
        primary_confidence: float,
        threshold: float = 0.4,
        image_bytes: bytes | None = None,
        text_hint: str | None = None,
    ) -> OCREngine | None:
        """단일 엔진 구성에서는 fallback을 사용하지 않는다."""
        del primary_engine, primary_confidence, threshold, image_bytes, text_hint
        return None
