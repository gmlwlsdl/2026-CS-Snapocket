"""Official PaddleOCR-VL document parser engine adapter."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import tempfile
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from PIL import Image

from app.services.ocr.base import OCREngine, OCREngineBusyError, OCREngineResult

logger = logging.getLogger(__name__)

PADDLE_DOC_PARSER_VERSION = "paddleocr-vl-doc-parser-v1"


class PaddleOCRVLDocParserEngine(OCREngine):
    """PaddleOCRVL pipeline wrapper using the official doc-parser path.

    The llama.cpp server is only used as PaddleOCR-VL's VLM recognition
    backend. Layout detection, reading order, element cropping, and document
    result assembly are delegated to the PaddleOCR package.
    """

    name = "paddle"
    expects_raw_document_image = True

    def __init__(
        self,
        *,
        enabled: bool = True,
        vl_rec_server_url: str = "http://llama-server:8080/v1",
        pipeline_version: str = "v1.5",
        device: str | None = None,
        engine: str | None = None,
        request_timeout_s: float = 300.0,
        availability_ttl_s: float = 15.0,
        use_doc_preprocessor: bool = True,
        use_layout_detection: bool = True,
        use_chart_recognition: bool = False,
        use_seal_recognition: bool = False,
        use_ocr_for_image_block: bool = True,
        format_block_content: bool = True,
        vl_rec_max_concurrency: int | None = None,
        max_new_tokens: int | None = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.vl_rec_server_url = self._normalize_v1_url(vl_rec_server_url)
        self.pipeline_version = str(pipeline_version or "v1.5").strip() or "v1.5"
        self.device = str(device or "").strip() or None
        self.engine = str(engine or "").strip() or None
        self.request_timeout_s = max(5.0, float(request_timeout_s))
        self.availability_ttl_s = max(1.0, float(availability_ttl_s))
        self.use_doc_preprocessor = bool(use_doc_preprocessor)
        self.use_layout_detection = bool(use_layout_detection)
        self.use_chart_recognition = bool(use_chart_recognition)
        self.use_seal_recognition = bool(use_seal_recognition)
        self.use_ocr_for_image_block = bool(use_ocr_for_image_block)
        self.format_block_content = bool(format_block_content)
        self.vl_rec_max_concurrency = (
            max(1, int(vl_rec_max_concurrency)) if vl_rec_max_concurrency is not None else None
        )
        self.max_new_tokens = max(32, int(max_new_tokens)) if max_new_tokens is not None else None

        self._lock = Lock()
        self._pipeline: Any | None = None
        self._last_error: str | None = None
        self._availability_cache: bool | None = None
        self._availability_checked_at = 0.0
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paddle-doc-parser")
        self._active_inference: Future[list[OCREngineResult]] | None = None

    @staticmethod
    def _normalize_v1_url(value: str) -> str:
        token = str(value or "").strip().rstrip("/")
        if not token:
            token = "http://llama-server:8080"
        if not token.startswith(("http://", "https://")):
            token = f"http://{token}"
        if not token.endswith("/v1"):
            token = f"{token}/v1"
        return token

    @property
    def _base_url(self) -> str:
        return self.vl_rec_server_url.removesuffix("/v1")

    def availability_detail(self) -> dict[str, Any]:
        with self._lock:
            return {
                "cached": self._availability_cache,
                "checked_at_monotonic": self._availability_checked_at,
                "last_error": self._last_error,
                "backend": "paddleocr-doc-parser",
                "vl_rec_backend": "llama-cpp-server",
                "vl_rec_server_url": self.vl_rec_server_url,
                "pipeline_version": self.pipeline_version,
                "device": self.device,
                "engine": self.engine,
                "prompt_version": PADDLE_DOC_PARSER_VERSION,
                "use_doc_preprocessor": self.use_doc_preprocessor,
                "use_layout_detection": self.use_layout_detection,
                "use_chart_recognition": self.use_chart_recognition,
                "use_seal_recognition": self.use_seal_recognition,
                "use_ocr_for_image_block": self.use_ocr_for_image_block,
                "format_block_content": self.format_block_content,
                "vl_rec_max_concurrency": self.vl_rec_max_concurrency,
                "max_new_tokens": self.max_new_tokens,
                "pipeline_loaded": self._pipeline is not None,
                "inflight": bool(self._active_inference is not None and not self._active_inference.done()),
            }

    def _request_json(self, path: str) -> dict[str, Any]:
        req = urlrequest.Request(url=f"{self._base_url}{path}", method="GET", headers={"Accept": "application/json"})
        try:
            with urlrequest.urlopen(req, timeout=min(self.request_timeout_s, 10.0)) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except urlerror.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
            raise RuntimeError(f"HTTP {exc.code}: {body[:240]}") from exc
        except urlerror.URLError as exc:
            raise RuntimeError(f"connection failed: {exc.reason}") from exc
        if not body.strip():
            return {}
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise RuntimeError("backend returned unexpected JSON shape")
        return parsed

    def _probe(self) -> bool:
        if not self.enabled:
            self._last_error = "PaddleOCR-VL doc parser is disabled"
            return False
        try:
            import paddleocr  # noqa: F401
        except Exception as exc:
            self._last_error = (
                "paddleocr[doc-parser] is not installed. "
                "Install paddlepaddle and paddleocr[doc-parser], then rebuild aiops-api. "
                f"import_error={exc}"
            )
            return False
        try:
            payload = self._request_json("/v1/models")
            rows = payload.get("data")
            if not isinstance(rows, list) or not rows:
                self._last_error = "llama.cpp /v1/models returned no models"
                return False
        except Exception as exc:
            self._last_error = f"llama.cpp VLM server unavailable: {exc}"
            return False
        self._last_error = None
        return True

    def probe(self) -> bool:
        ok = self._probe()
        with self._lock:
            self._availability_cache = ok
            self._availability_checked_at = time.monotonic()
        return ok

    def available(self) -> bool:
        with self._lock:
            checked_at = self._availability_checked_at
            cached = self._availability_cache
        if cached is not None and (time.monotonic() - checked_at) < self.availability_ttl_s:
            return cached
        return self.probe()

    def _ensure_pipeline(self):
        with self._lock:
            if self._pipeline is not None:
                return self._pipeline
        if not self.available():
            raise RuntimeError(self._last_error or "PaddleOCR-VL doc parser unavailable")

        from paddleocr import PaddleOCRVL

        kwargs: dict[str, Any] = {
            "pipeline_version": self.pipeline_version,
            "vl_rec_backend": "llama-cpp-server",
            "vl_rec_server_url": self.vl_rec_server_url,
            "use_layout_detection": self.use_layout_detection,
            "use_chart_recognition": self.use_chart_recognition,
            "use_seal_recognition": self.use_seal_recognition,
            "use_ocr_for_image_block": self.use_ocr_for_image_block,
            "format_block_content": self.format_block_content,
        }
        if self.vl_rec_max_concurrency is not None:
            kwargs["vl_rec_max_concurrency"] = self.vl_rec_max_concurrency
        if self.device:
            kwargs["device"] = self.device
        if self.engine:
            kwargs["engine"] = self.engine

        try:
            pipeline = PaddleOCRVL(**kwargs)
        except TypeError:
            # Keep compatibility with slightly older PaddleOCR wheels that may
            # not expose every v1.5 keyword yet.
            minimal = {
                "pipeline_version": self.pipeline_version,
                "vl_rec_backend": "llama-cpp-server",
                "vl_rec_server_url": self.vl_rec_server_url,
            }
            if self.vl_rec_max_concurrency is not None:
                minimal["vl_rec_max_concurrency"] = self.vl_rec_max_concurrency
            if self.device:
                minimal["device"] = self.device
            if self.engine:
                minimal["engine"] = self.engine
            pipeline = PaddleOCRVL(**minimal)

        with self._lock:
            self._pipeline = pipeline
        return pipeline

    def warmup(self) -> bool:
        self._ensure_pipeline()
        return True

    def unload(self) -> bool:
        with self._lock:
            if self._active_inference is not None and not self._active_inference.done():
                return False
            self._pipeline = None
        return True

    @staticmethod
    def _write_image(image_bytes: bytes) -> str:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        path = handle.name
        handle.close()
        image.save(path, format="PNG")
        return path

    @staticmethod
    def _read_saved_json(res: Any, source_path: str) -> dict[str, Any] | None:
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                res.save_to_json(save_path=tmpdir)
            except Exception:
                return None
            candidates = sorted(Path(tmpdir).glob("*.json"))
            if not candidates:
                stem = Path(source_path).stem
                candidates = sorted(Path(tmpdir).glob(f"{stem}*_res.json"))
            if not candidates:
                return None
            try:
                return json.loads(candidates[0].read_text(encoding="utf-8"))
            except Exception:
                return None

    @classmethod
    def _result_to_dict(cls, res: Any, source_path: str) -> dict[str, Any]:
        if type(res) is dict:
            inner = res.get("res")
            return inner if isinstance(inner, dict) else res
        for attr in ("json", "res", "data", "_data"):
            value = getattr(res, attr, None)
            if isinstance(value, dict):
                inner = value.get("res")
                return inner if isinstance(inner, dict) else value
        to_dict = getattr(res, "to_dict", None)
        if callable(to_dict):
            try:
                value = to_dict()
                if isinstance(value, dict):
                    inner = value.get("res")
                    return inner if isinstance(inner, dict) else value
            except Exception:
                pass
        try:
            value = dict(res)
            if isinstance(value, dict):
                inner = value.get("res")
                return inner if isinstance(inner, dict) else value
        except Exception:
            pass
        saved = cls._read_saved_json(res, source_path)
        if saved:
            return saved
        return {}

    @staticmethod
    def _coerce_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return "\n".join(PaddleOCRVLDocParserEngine._coerce_text(v) for v in value).strip()
        if isinstance(value, dict):
            for key in ("text", "content", "markdown", "value"):
                text = PaddleOCRVLDocParserEngine._coerce_text(value.get(key))
                if text:
                    return text
        return str(value).strip()

    @staticmethod
    def _strip_markdown_heading(value: str) -> str:
        return re.sub(r"^\s{0,3}#{1,6}\s+", "", str(value or "").strip())

    @staticmethod
    def _coerce_bbox(value: Any) -> list[float] | None:
        if value is None:
            return None
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, tuple):
            value = list(value)
        if not isinstance(value, list) or not value:
            return None
        if all(isinstance(v, (int, float)) for v in value[:4]) and len(value) >= 4:
            return [float(value[0]), float(value[1]), float(value[2]), float(value[3])]

        points: list[tuple[float, float]] = []
        for item in value:
            if hasattr(item, "tolist"):
                item = item.tolist()
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                try:
                    points.append((float(item[0]), float(item[1])))
                except Exception:
                    continue
        if not points:
            return None
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return [min(xs), min(ys), max(xs), max(ys)]

    @staticmethod
    def _normalize_block_type(label: Any) -> str:
        token = str(label or "text").strip().lower()
        if "table" in token:
            return "table"
        if "title" in token or "heading" in token:
            return "title"
        if "header" in token:
            return "header"
        if "footer" in token or "page_number" in token or token == "number":
            return "footer"
        if "formula" in token or "equation" in token:
            return "text"
        if "image" in token or "chart" in token or "figure" in token:
            return "text"
        if "form" in token or "key" in token:
            return "form"
        return "text"

    @classmethod
    def _extract_blocks(cls, data: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = data.get("parsing_res_list")
        if isinstance(candidates, list):
            return [cls._object_to_block_dict(item) for item in candidates if cls._object_to_block_dict(item)]
        for key in ("blocks", "layout", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [cls._object_to_block_dict(item) for item in value if cls._object_to_block_dict(item)]
        markdown_text = cls._coerce_text(data.get("markdown") or data.get("markdown_text"))
        if markdown_text:
            return [{"block_content": markdown_text, "block_label": "text", "block_order": 1}]
        return []

    @staticmethod
    def _object_to_block_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        out: dict[str, Any] = {}
        for source, target in (
            ("block_label", "block_label"),
            ("label", "block_label"),
            ("block_content", "block_content"),
            ("content", "block_content"),
            ("block_bbox", "block_bbox"),
            ("bbox", "block_bbox"),
            ("block_order", "block_order"),
            ("order", "block_order"),
        ):
            item = getattr(value, source, None)
            if item is not None:
                out[target] = item
        return out

    @classmethod
    def _blocks_to_results(cls, page_data: dict[str, Any], *, page_no: int) -> list[OCREngineResult]:
        raw_blocks = cls._extract_blocks(page_data)
        results: list[OCREngineResult] = []
        collected_text: list[str] = []
        title = ""

        for idx, block in enumerate(raw_blocks, start=1):
            text = cls._coerce_text(
                block.get("block_content")
                or block.get("content")
                or block.get("text")
                or block.get("rec_text")
                or block.get("markdown")
            )
            if not text:
                continue
            label = block.get("block_label") or block.get("label") or block.get("type")
            block_type = cls._normalize_block_type(label)
            if block_type == "title":
                text = "\n".join(cls._strip_markdown_heading(line) for line in text.splitlines()).strip()
            order_value = block.get("block_order") or block.get("order") or block.get("reading_order") or idx
            try:
                reading_order = int(order_value)
            except Exception:
                reading_order = idx
            bbox = cls._coerce_bbox(block.get("block_bbox") or block.get("bbox") or block.get("poly"))
            if block_type == "title" and not title:
                title = text.splitlines()[0].strip()
            collected_text.append(text)
            results.append(
                OCREngineResult(
                    text=text,
                    confidence=0.9,
                    bbox=bbox,
                    page_no=page_no,
                    block_type=block_type,
                    reading_order=reading_order,
                    table_id=f"p{page_no}-tbl{idx}" if block_type == "table" else None,
                )
            )

        if not results:
            fallback = cls._coerce_text(page_data.get("text") or page_data.get("raw_text") or page_data.get("content"))
            if fallback:
                collected_text.append(fallback)
                results.append(
                    OCREngineResult(
                        text=fallback,
                        confidence=0.75,
                        bbox=None,
                        page_no=page_no,
                        block_type="text",
                        reading_order=1,
                    )
                )

        raw_text = "\n".join(t for t in collected_text if t.strip()).strip()
        if results and raw_text:
            if not title:
                title = next((line.strip() for line in raw_text.splitlines() if line.strip()), "")
            results[0].structured_payload = {
                "raw_text": raw_text,
                "title": title,
                "category": "",
                "summary": "",
                "tags": [],
                "key_concepts": [],
                "capture_date": None,
                "deadline": None,
            }
        return results

    def infer_image(self, image_bytes: bytes, page_no: int = 1) -> list[OCREngineResult]:
        if not image_bytes:
            raise RuntimeError("empty image payload")
        source_path = ""
        try:
            pipeline = self._ensure_pipeline()
            source_path = self._write_image(image_bytes)
            predict_kwargs: dict[str, Any] = {}
            if self.max_new_tokens is not None:
                predict_kwargs["max_new_tokens"] = self.max_new_tokens
            output = pipeline.predict(source_path, **predict_kwargs)
            page_results: list[OCREngineResult] = []
            for result in output:
                data = self._result_to_dict(result, source_path)
                page_results.extend(self._blocks_to_results(data, page_no=page_no))
            if not page_results:
                raise RuntimeError("empty OCR output from PaddleOCRVL doc parser")
            return page_results
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc) or repr(exc)
                self._availability_cache = False
                self._availability_checked_at = time.monotonic()
            raise RuntimeError(f"paddle OCR failed: {exc}") from exc
        finally:
            if source_path:
                try:
                    Path(source_path).unlink(missing_ok=True)
                except Exception:
                    pass

    async def infer_image_async(
        self,
        image_bytes: bytes,
        page_no: int = 1,
    ) -> list[OCREngineResult]:
        with self._lock:
            if self._active_inference is not None and not self._active_inference.done():
                raise OCREngineBusyError(
                    "paddle inference already running. Wait for completion and retry."
                )
            future: Future[list[OCREngineResult]] = self._executor.submit(
                self.infer_image, image_bytes, page_no
            )
            self._active_inference = future

        def _clear_inflight(done_future: Future[list[OCREngineResult]]) -> None:
            with self._lock:
                if self._active_inference is done_future:
                    self._active_inference = None

        future.add_done_callback(_clear_inflight)
        return await asyncio.wrap_future(future)
