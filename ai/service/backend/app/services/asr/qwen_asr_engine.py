"""Qwen3-ASR 기반 오디오 전사 엔진."""

from __future__ import annotations

import asyncio
import importlib.util
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Lock


@dataclass(frozen=True)
class ASRTranscription:
    text: str
    language: str
    confidence: float


class QwenASREngine:
    """`qwen-asr` 패키지를 지연 로드해 MP3 전사를 수행한다."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        model_name: str = "Qwen/Qwen3-ASR-1.7B",
        language: str = "Korean",
        max_new_tokens: int = 1024,
        dtype: str = "float16",
        device_map: str = "cpu",
        low_cpu_mem_usage: bool = True,
    ) -> None:
        self.enabled = bool(enabled)
        self.model_name = str(model_name or "").strip() or "Qwen/Qwen3-ASR-1.7B"
        self.language = str(language or "").strip() or "Korean"
        self.max_new_tokens = max(32, int(max_new_tokens))
        self.dtype = str(dtype or "float16").strip().lower()
        self.device_map = str(device_map or "cpu").strip()
        self.low_cpu_mem_usage = bool(low_cpu_mem_usage)

        self._lock = Lock()
        self._model = None
        self._last_error: str | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qwen-asr")

    def availability_detail(self) -> dict[str, str | bool]:
        return {
            "enabled": self.enabled,
            "model_name": self.model_name,
            "language": self.language,
            "max_new_tokens": str(self.max_new_tokens),
            "dtype": self.dtype,
            "device_map": self.device_map,
            "low_cpu_mem_usage": self.low_cpu_mem_usage,
            "last_error": self._last_error or "",
            "runtime": "qwen-asr",
        }

    def available(self) -> bool:
        if not self.enabled:
            self._last_error = "Qwen ASR is disabled"
            return False
        if importlib.util.find_spec("qwen_asr") is None:
            self._last_error = "qwen-asr package is not installed"
            return False
        self._last_error = None
        return True

    def _resolve_dtype(self):
        try:
            import torch
        except Exception:
            return None
        token = self.dtype
        if token in {"float16", "fp16", "half"}:
            return torch.float16
        if token in {"bfloat16", "bf16"}:
            return torch.bfloat16
        if token in {"float32", "fp32"}:
            return torch.float32
        return None

    def _load_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from qwen_asr import Qwen3ASRModel
            except Exception as exc:
                self._last_error = f"qwen_asr import failed: {exc}"
                raise RuntimeError(self._last_error) from exc
            try:
                kwargs = {"max_new_tokens": self.max_new_tokens}
                dtype_obj = self._resolve_dtype()
                if dtype_obj is not None:
                    kwargs["dtype"] = dtype_obj
                if self.device_map:
                    kwargs["device_map"] = self.device_map
                kwargs["low_cpu_mem_usage"] = self.low_cpu_mem_usage
                try:
                    self._model = Qwen3ASRModel.from_pretrained(self.model_name, **kwargs)
                except TypeError:
                    # 일부 버전은 인자 호환성이 달라서 최소 인자 세트로 재시도한다.
                    fallback = {
                        "max_new_tokens": self.max_new_tokens,
                    }
                    if dtype_obj is not None:
                        fallback["dtype"] = dtype_obj
                    if self.device_map:
                        fallback["device_map"] = self.device_map
                    self._model = Qwen3ASRModel.from_pretrained(self.model_name, **fallback)
            except Exception as exc:
                self._last_error = f"Qwen ASR model load failed: {exc}"
                raise RuntimeError(self._last_error) from exc
            return self._model

    def transcribe(self, *, audio_bytes: bytes, filename: str) -> ASRTranscription:
        if not self.available():
            raise RuntimeError(self._last_error or "Qwen ASR runtime unavailable")
        model = self._load_model()
        suffix = Path(filename or "audio.mp3").suffix.lower() or ".mp3"
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                temp_path = tmp.name

            outputs = model.transcribe(
                audio=temp_path,
                language=self.language,
            )
            first = outputs[0] if outputs else None
            text = str(getattr(first, "text", "") or "").strip()
            language = str(getattr(first, "language", "") or "").strip() or self.language
            confidence = float(getattr(first, "confidence", 0.9) or 0.9)
            if not text:
                raise RuntimeError("Qwen ASR returned empty transcription")
            return ASRTranscription(
                text=text,
                language=language,
                confidence=max(0.0, min(1.0, confidence)),
            )
        except Exception as exc:
            self._last_error = str(exc) or repr(exc)
            raise
        finally:
            if temp_path:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    pass

    async def transcribe_async(self, *, audio_bytes: bytes, filename: str) -> ASRTranscription:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            lambda: self.transcribe(audio_bytes=audio_bytes, filename=filename),
        )
