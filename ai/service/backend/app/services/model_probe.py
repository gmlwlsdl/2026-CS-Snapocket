"""OCR 엔진 가용성을 주기적으로 갱신하는 백그라운드 프로버."""

from __future__ import annotations

import threading
from typing import Protocol


class ProbedEngine(Protocol):
    def probe(self) -> bool:
        ...


class ModelAvailabilityProber:
    def __init__(self, engines: list[ProbedEngine], interval_s: float = 15.0) -> None:
        self.engines = engines
        self.interval_s = max(1.0, float(interval_s))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """프로빙 스레드를 시작한다(이미 실행 중이면 no-op)."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="model-availability-prober", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """프로빙 스레드를 종료한다."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def _run(self) -> None:
        # 시작 시 1회 즉시 프로빙하여 캐시를 워밍업한다.
        self._probe_once()

        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=self.interval_s):
                break
            self._probe_once()

    def _probe_once(self) -> None:
        for engine in self.engines:
            try:
                engine.probe()
            except Exception:
                # 프로버 실패가 전체 프로세스를 중단시키지 않도록 예외를 삼킨다.
                pass
