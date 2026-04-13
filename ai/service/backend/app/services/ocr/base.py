"""OCR 엔진 추상 계약과 공통 결과 스키마."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OCREngineResult:
    text: str
    confidence: float
    bbox: list[float] | None
    page_no: int
    block_type: str = "text"
    parent_block_id: str | None = None
    reading_order: int | None = None
    table_id: str | None = None
    row_idx: int | None = None
    col_idx: int | None = None
    rowspan: int | None = None
    colspan: int | None = None


class OCREngineBusyError(RuntimeError):
    """OCR 엔진이 이미 다른 요청을 처리 중일 때 발생."""


class OCREngine(ABC):
    name: str

    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def infer_image(self, image_bytes: bytes, page_no: int = 1) -> list[OCREngineResult]:
        raise NotImplementedError

    async def infer_image_async(
        self, image_bytes: bytes, page_no: int = 1
    ) -> list[OCREngineResult]:
        """기본 구현: 동기 infer를 executor로 감싸 비동기 인터페이스를 제공한다."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.infer_image, image_bytes, page_no)

    def warmup(self) -> bool:
        """선택적 런타임 warm-up 훅. 엔진 구현체에서 오버라이드 가능."""
        return True

    def unload(self) -> bool:
        """선택적 런타임 unload 훅. 엔진 구현체에서 오버라이드 가능."""
        return True
