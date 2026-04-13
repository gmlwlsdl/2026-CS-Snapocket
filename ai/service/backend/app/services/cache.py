"""SHA-256 파일 해시 기반의 TTL 결과 캐시."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from cachetools import TTLCache


class ResultCache:
    """OCR 결과를 짧게 재사용하기 위한 메모리 캐시.

    동일 파일 바이트(및 scope)에 대해 이전 결과를 반환해
    중복 추론 비용을 줄인다.
    """

    def __init__(self, maxsize: int = 500, ttl: int = 3600) -> None:
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)

    @staticmethod
    def _key(file_bytes: bytes, scope: str = "") -> str:
        # scope를 키에 포함해 엔진/옵션별 캐시 충돌을 방지한다.
        scope_bytes = scope.encode("utf-8")
        return hashlib.sha256(scope_bytes + b"\0" + file_bytes).hexdigest()

    def get(self, file_bytes: bytes, *, scope: str = "") -> dict[str, Any] | None:
        result = self._cache.get(self._key(file_bytes, scope=scope))
        if result is None:
            return None
        return copy.deepcopy(result)

    def set(self, file_bytes: bytes, result: dict[str, Any], *, scope: str = "") -> None:
        self._cache[self._key(file_bytes, scope=scope)] = copy.deepcopy(result)

    @property
    def size(self) -> int:
        return len(self._cache)
