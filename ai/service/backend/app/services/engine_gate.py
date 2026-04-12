"""OCR 엔진별 동시 실행을 제한하는 비차단 게이트."""

from __future__ import annotations

from threading import Lock


class EngineRequestGate:
    """엔진 이름(`paddle`/`glm`)별 간단한 mutex 래퍼."""

    def __init__(self) -> None:
        self._locks: dict[str, Lock] = {
            "paddle": Lock(),
            "glm": Lock(),
        }

    def try_acquire(self, engine: str) -> bool:
        """엔진 락을 비차단으로 획득 시도한다."""
        key = str(engine or "").strip().lower()
        lock = self._locks.get(key)
        if lock is None:
            # 알 수 없는 엔진은 여기서 막지 않는다.
            return True
        return lock.acquire(blocking=False)

    def release(self, engine: str) -> None:
        """획득된 엔진 락을 해제한다."""
        key = str(engine or "").strip().lower()
        lock = self._locks.get(key)
        if lock is None:
            return
        if lock.locked():
            lock.release()
