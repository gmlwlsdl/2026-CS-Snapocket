"""업로드 파일 악성코드 점검 훅(시그니처 + 외부 스캐너 명령)."""

from __future__ import annotations

import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


_EICAR_SIGNATURE = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$"
    b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)


@dataclass
class ScanResult:
    safe: bool
    code: str | None = None
    message: str | None = None


class MalwareScanner:
    def __init__(
        self,
        *,
        enabled: bool,
        command: str = "",
        timeout_s: float = 5.0,
    ) -> None:
        self.enabled = enabled
        self.command = command.strip()
        self.timeout_s = max(1.0, float(timeout_s))

    def scan(self, *, filename: str, payload: bytes) -> ScanResult:
        """업로드 payload를 검사하고 안전 여부를 반환한다."""
        if not self.enabled:
            return ScanResult(safe=True)

        # CI/로컬 검증용 EICAR 시그니처 기본 체크.
        if _EICAR_SIGNATURE in payload:
            return ScanResult(
                safe=False,
                code="MALWARE_DETECTED",
                message="EICAR test signature detected",
            )

        if not self.command:
            # 외부 스캐너 명령이 없으면 시그니처 기반 점검만 수행한다.
            return ScanResult(safe=True)

        return self._scan_with_external_command(filename=filename, payload=payload)

    def _scan_with_external_command(self, *, filename: str, payload: bytes) -> ScanResult:
        """외부 스캐너 명령을 실행해 정밀 검사를 수행한다."""
        suffix = Path(filename).suffix or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)

        try:
            cmd = self.command
            if "{file}" in cmd:
                cmd = cmd.replace("{file}", str(tmp_path))
                args = shlex.split(cmd)
            else:
                args = shlex.split(cmd) + [str(tmp_path)]

            proc = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout_s,
            )
            if proc.returncode == 0:
                return ScanResult(safe=True)

            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            detail = stderr or stdout or f"scanner exit code {proc.returncode}"
            return ScanResult(safe=False, code="MALWARE_DETECTED", message=detail[:500])
        except FileNotFoundError:
            return ScanResult(
                safe=False,
                code="MALWARE_SCAN_FAILED",
                message="scanner command not found",
            )
        except subprocess.TimeoutExpired:
            return ScanResult(
                safe=False,
                code="MALWARE_SCAN_FAILED",
                message=f"scanner timeout ({self.timeout_s:.1f}s)",
            )
        except Exception as exc:
            return ScanResult(
                safe=False,
                code="MALWARE_SCAN_FAILED",
                message=str(exc)[:500],
            )
        finally:
            tmp_path.unlink(missing_ok=True)
