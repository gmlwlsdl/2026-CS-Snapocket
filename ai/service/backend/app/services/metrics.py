"""Prometheus 텍스트 내보내기를 지원하는 경량 메모리 메트릭 저장소."""

from __future__ import annotations

from collections import defaultdict
import math
from threading import Lock


class MetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._observations: dict[str, list[float]] = defaultdict(list)

    def inc(self, name: str, value: float = 1.0) -> None:
        """카운터형 메트릭을 증가시킨다."""
        with self._lock:
            self._counters[name] += value

    def snapshot(self) -> dict[str, float]:
        """현재 카운터 스냅샷을 사본으로 반환한다."""
        with self._lock:
            return dict(self._counters)

    def observe(self, name: str, value: float) -> None:
        """분포형 메트릭 샘플(관측값)을 추가한다."""
        with self._lock:
            if math.isfinite(value):
                self._observations[name].append(float(value))

    def _observation_summary(self) -> dict[str, dict[str, float]]:
        with self._lock:
            copied = {k: list(v) for k, v in self._observations.items()}
        summary: dict[str, dict[str, float]] = {}
        for key, values in copied.items():
            if not values:
                continue
            values.sort()
            count = len(values)
            p50_idx = min(count - 1, int(round((count - 1) * 0.50)))
            p95_idx = min(count - 1, int(round((count - 1) * 0.95)))
            summary[key] = {
                "count": float(count),
                "sum": float(sum(values)),
                "p50": float(values[p50_idx]),
                "p95": float(values[p95_idx]),
            }
        return summary

    def to_prometheus(self) -> str:
        """카운터/요약 통계를 Prometheus exposition format으로 변환한다."""
        lines: list[str] = []
        snapshot = self.snapshot()
        for key, value in sorted(snapshot.items()):
            metric_name = key.replace("-", "_").replace(".", "_")
            lines.append(f"# TYPE {metric_name} counter")
            lines.append(f"{metric_name} {value}")

        # 파생 메트릭: 캐시 적중률.
        hit = float(snapshot.get("cache_hit_total", 0.0))
        miss = float(snapshot.get("cache_miss_total", 0.0))
        total = hit + miss
        if total > 0:
            lines.append("# TYPE pipeline_cache_hit_ratio gauge")
            lines.append(f"pipeline_cache_hit_ratio {hit / total:.6f}")

        for key, stats in sorted(self._observation_summary().items()):
            metric_name = key.replace("-", "_").replace(".", "_")
            lines.append(f"# TYPE {metric_name}_count gauge")
            lines.append(f"{metric_name}_count {stats['count']}")
            lines.append(f"# TYPE {metric_name}_sum gauge")
            lines.append(f"{metric_name}_sum {stats['sum']:.6f}")
            lines.append(f"# TYPE {metric_name}_p50 gauge")
            lines.append(f"{metric_name}_p50 {stats['p50']:.6f}")
            lines.append(f"# TYPE {metric_name}_p95 gauge")
            lines.append(f"{metric_name}_p95 {stats['p95']:.6f}")
        return "\n".join(lines) + "\n"
