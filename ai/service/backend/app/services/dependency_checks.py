"""ready/status 엔드포인트에서 사용하는 의존성 헬스체크 유틸."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class CheckResult:
    configured: bool
    ok: bool
    error: str | None = None


def ping_redis(redis_url: str | None, timeout_s: float = 1.5) -> CheckResult:
    """Redis 연결 가능 여부를 최소 프로토콜로 점검한다."""
    if not redis_url:
        return CheckResult(configured=False, ok=True, error=None)

    parsed = urlparse(redis_url)
    host = parsed.hostname
    port = parsed.port or 6379
    if not host:
        return CheckResult(configured=True, ok=False, error="invalid redis url")

    password = parsed.password

    try:
        with socket.create_connection((host, port), timeout=timeout_s) as conn:
            conn.settimeout(timeout_s)
            if password:
                # redis-py 없이도 인증 여부를 확인하기 위한 최소 RESP AUTH.
                encoded = password.encode("utf-8")
                auth_cmd = (
                    f"*2\r\n$4\r\nAUTH\r\n${len(encoded)}\r\n".encode("utf-8")
                    + encoded
                    + b"\r\n"
                )
                conn.sendall(auth_cmd)
                auth_reply = conn.recv(256)
                if not auth_reply.startswith(b"+OK"):
                    return CheckResult(configured=True, ok=False, error="redis auth failed")

            # 경량 상태 확인용 PING 명령.
            conn.sendall(b"*1\r\n$4\r\nPING\r\n")
            reply = conn.recv(256)
            if reply.startswith(b"+PONG"):
                return CheckResult(configured=True, ok=True, error=None)
            return CheckResult(configured=True, ok=False, error=f"unexpected redis reply: {reply!r}")
    except Exception as exc:  # pragma: no cover - env-dependent
        return CheckResult(configured=True, ok=False, error=str(exc))
