"""메모리+영속 저장소 기반 idempotency 재실행 방지 스토어."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.services.persistence import PersistenceStore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _CacheEntry:
    request_hash: str
    response_data: dict | list | None
    created_at: datetime


class IdempotencyConflictError(ValueError):
    """같은 키에 서로 다른 요청 본문이 들어온 경우 발생."""
    pass


class IdempotencyStore:
    def __init__(
        self,
        *,
        ttl_s: int,
        persistence: PersistenceStore | None = None,
    ) -> None:
        self.ttl_s = ttl_s
        self.persistence = persistence
        self._lock = Lock()
        # 빠른 응답을 위한 메모리 전면 캐시. 영속 저장소를 최종 기준으로 사용한다.
        self._cache: dict[str, _CacheEntry] = {}

    def get(
        self,
        *,
        route: str,
        key: str,
        request_hash: str,
    ) -> dict | list | None:
        """요청 해시가 일치하면 이전 응답을 반환하고, 불일치면 충돌 예외를 던진다."""
        storage_key = self._storage_key(route, key)
        self._evict_expired()

        with self._lock:
            entry = self._cache.get(storage_key)

        if entry is None and self.persistence is not None:
            # 프로세스 재시작 이후에도 재생(replay) 가능하도록 DB fallback 조회.
            persisted = self.persistence.get_idempotency(
                route=route,
                idempotency_key=key,
                ttl_s=self.ttl_s,
            )
            if persisted is not None:
                entry = _CacheEntry(
                    request_hash=persisted.request_hash,
                    response_data=persisted.response_data,
                    created_at=persisted.created_at,
                )
                with self._lock:
                    self._cache[storage_key] = entry

        if entry is None:
            return None

        # 같은 키는 반드시 동일한 요청 fingerprint를 가져야 한다.
        if entry.request_hash != request_hash:
            raise IdempotencyConflictError("idempotency key reused with different payload")

        return entry.response_data

    def put(
        self,
        *,
        route: str,
        key: str,
        request_hash: str,
        response_data: dict | list | None,
    ) -> None:
        """idempotency 키와 요청 해시, 응답 본문을 저장한다."""
        storage_key = self._storage_key(route, key)
        entry = _CacheEntry(
            request_hash=request_hash,
            response_data=response_data,
            created_at=_utcnow(),
        )

        with self._lock:
            self._cache[storage_key] = entry

        if self.persistence is not None:
            # 서버 재시작 이후 재생을 위해 영속 저장소에도 기록한다.
            self.persistence.put_idempotency(
                route=route,
                idempotency_key=key,
                request_hash=request_hash,
                response_data=response_data,
            )

    def _evict_expired(self) -> None:
        """TTL이 지난 엔트리를 메모리 캐시에서 제거한다."""
        threshold = _utcnow() - timedelta(seconds=self.ttl_s)
        with self._lock:
            stale = [key for key, item in self._cache.items() if item.created_at < threshold]
            for key in stale:
                self._cache.pop(key, None)

    @staticmethod
    def _storage_key(route: str, key: str) -> str:
        """엔드포인트(route)별 key namespace를 분리한다."""
        return f"{route}:{key}"
