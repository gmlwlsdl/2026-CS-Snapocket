"""설정과 서비스 객체를 조합해 앱 상태(AppState)를 구성하는 루트 모듈."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings, load_settings
from app.services.engine_gate import EngineRequestGate
from app.services.idempotency import IdempotencyStore
from app.services.job_manager import JobManager
from app.services.metrics import MetricsStore
from app.services.cache import ResultCache
from app.services.dispatch_service import DispatchService
from app.services.image_processor import ImageProcessor
from app.services.log_buffer import LogBuffer, attach_to_logger
from app.services.model_probe import ModelAvailabilityProber
from app.services.model_registry import ModelRegistry
from app.services.asr.qwen_asr_engine import QwenASREngine
from app.services.ocr.llamacpp_engine import LlamaCppVisionEngine
from app.services.ocr.router import OCREngineRouter
from app.services.persistence import PersistenceStore
from app.services.pipeline import InferencePipeline
from app.services.redis_queue import RedisJobManager
from app.services.security_scan import MalwareScanner
from app.services.secret_cipher import SecretCipher
from app.services.server_registry import ServerRegistry

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    settings: Settings
    metrics: MetricsStore
    persistence: PersistenceStore
    model_registry: ModelRegistry
    job_manager: Any
    idempotency: IdempotencyStore
    scanner: MalwareScanner
    router: OCREngineRouter
    pipeline: InferencePipeline
    log_buffer: LogBuffer = None  # type: ignore[assignment]
    model_prober: ModelAvailabilityProber | None = None
    engine_gate: EngineRequestGate | None = None
    server_registry: ServerRegistry | None = None
    dispatch: DispatchService | None = None


def _is_valid_qwen_asr_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if not (path / "config.json").exists():
        return False
    has_weights = any(path.glob("model-*.safetensors"))
    return has_weights


def _resolve_qwen_asr_model_ref(settings: Settings) -> str:
    """로컬 ASR 모델 디렉터리를 우선 탐지하고, 없으면 설정값을 사용한다."""
    ai_root = Path(__file__).resolve().parents[4]
    model_root = ai_root / "model"

    # 로컬 1.7B 계열 폴더를 우선 탐지한다.
    preferred_dirs = [
        model_root / "Qwen3-ASR-1.7B",
    ]
    for candidate in preferred_dirs:
        if _is_valid_qwen_asr_dir(candidate):
            return str(candidate.resolve())

    configured = str(settings.qwen_asr_model or "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.exists() and _is_valid_qwen_asr_dir(configured_path):
            return str(configured_path.resolve())
        if not configured_path.is_absolute():
            relative_to_ai = (ai_root / configured_path).resolve()
            if _is_valid_qwen_asr_dir(relative_to_ai):
                return str(relative_to_ai)
        return configured

    # 로컬/설정 모두 없으면 1.7B HF 모델명을 최후 fallback으로 사용한다.
    return "Qwen/Qwen3-ASR-1.7B"


def build_app_state() -> AppState:
    """환경 설정을 읽어 서비스 의존성을 초기화하고 AppState를 반환한다."""
    settings = load_settings()
    log_buffer = LogBuffer(maxlen=500)
    attach_to_logger(log_buffer, "app")
    metrics = MetricsStore()
    # 운영/로컬 환경 모두 동일한 인터페이스를 쓰고, 저장소만 환경별로 분기한다.
    persistence = PersistenceStore(
        database_url=settings.database_url,
        enabled=settings.database_enable,
    )
    persistence.start()
    # 후처리 category가 항상 DB 기반 목록에서 선택되도록 최소 기본값을 보장한다.
    persistence.ensure_default_categories(["unknown"])

    # 모델 활성화 상태와 이력은 재시작 후에도 유지되어야 하므로 영속 계층과 직접 연결한다.
    model_registry = ModelRegistry(persistence=persistence)
    idempotency = IdempotencyStore(
        ttl_s=settings.idempotency_ttl_s,
        persistence=persistence,
    )

    # 현재 로컬 OCR 런타임은 paddle gguf 단일 엔진만 사용한다.
    paddle_engine = LlamaCppVisionEngine(
        name="paddle",
        model=settings.llm_model_paddle,
        profile="paddle",
        enabled=settings.paddle_enable,
        base_url=settings.llm_base_url,
        availability_ttl_s=settings.model_availability_ttl_s,
        request_timeout_s=settings.llm_request_timeout_s,
        keep_alive=settings.llm_keep_alive,
        temperature=settings.llm_temperature,
        max_side_px=settings.llm_image_max_side_px,
        max_tokens=settings.llm_max_tokens,
    )
    router = OCREngineRouter(
        paddle_engine=paddle_engine,
        default_engine="paddle",
        performance_provider=model_registry.engine_runtime_stats,
    )
    qwen_asr_model_ref = _resolve_qwen_asr_model_ref(settings)
    qwen_asr_engine = QwenASREngine(
        enabled=settings.qwen_asr_enable,
        model_name=qwen_asr_model_ref,
        language=settings.qwen_asr_language,
        max_new_tokens=settings.qwen_asr_max_new_tokens,
    )
    preprocessor = ImageProcessor(
        enabled=settings.image_preprocess,
        target_dpi=settings.image_target_dpi,
        assumed_input_dpi=settings.image_assumed_input_dpi,
        apply_otsu=settings.image_apply_otsu,
        max_side_px=settings.image_max_side_px,
    )
    cache = ResultCache(maxsize=500, ttl=3600)
    pipeline = InferencePipeline(
        router,
        prefer_embedded_pdf_text=settings.prefer_embedded_pdf_text,
        image_preprocessor=preprocessor,
        result_cache=cache,
        max_concurrency=settings.ocr_concurrency,
        metrics=metrics,
        vlm_ocr_verify_langs=settings.local_model_hint_ocr_langs,
        vlm_ocr_verify_timeout_s=settings.local_model_hint_ocr_timeout_s,
        vlm_ocr_verify_max_chars=settings.local_model_hint_ocr_max_chars,
        category_provider=lambda: persistence.list_categories(enabled_only=True),
        qwen_asr_engine=qwen_asr_engine,
    )
    if settings.job_queue_backend.lower() == "redis" and settings.redis_enable:
        try:
            job_manager = RedisJobManager(
                redis_url=settings.redis_url,
                task_handlers={"pipeline.process": pipeline.process},
                max_workers=1,
                timeout_s=settings.job_timeout_s,
                max_retries=settings.job_max_retries,
                retry_backoff_s=settings.job_retry_backoff_s,
                persistence=persistence,
            )
            logger.info("Job queue backend: redis")
        except Exception as exc:
            # Redis 사용 불가 시 자동으로 메모리 큐로 폴백한다.
            logger.warning("Redis queue unavailable; fallback to memory queue: %s", exc)
            job_manager = JobManager(
                max_workers=2,
                timeout_s=settings.job_timeout_s,
                max_retries=settings.job_max_retries,
                retry_backoff_s=settings.job_retry_backoff_s,
                persistence=persistence,
            )
            metrics.inc("job_queue_fallback_total")
    else:
        job_manager = JobManager(
            max_workers=2,
            timeout_s=settings.job_timeout_s,
            max_retries=settings.job_max_retries,
            retry_backoff_s=settings.job_retry_backoff_s,
            persistence=persistence,
        )
        logger.info("Job queue backend: memory")

    scanner = MalwareScanner(
        enabled=settings.malware_scan_enable,
        command=settings.malware_scan_command,
        timeout_s=settings.malware_scan_timeout_s,
    )

    cipher = SecretCipher(settings.aiops_server_secret_key)
    server_registry = ServerRegistry(
        persistence=persistence,
        cipher=cipher,
        allow_public_endpoints=settings.allow_public_server_endpoints,
        allow_hostname_endpoints=settings.allow_hostname_server_endpoints,
        allow_zrok_endpoints=settings.allow_zrok_server_endpoints,
    )
    dispatch = DispatchService(
        server_registry=server_registry,
        pipeline=pipeline,
        job_manager=job_manager,
        settings=settings,
        router=router,
        request_timeout_s=settings.dispatch_upstream_timeout_s,
    )
    model_prober = None
    if settings.model_probe_enable:
        model_prober = ModelAvailabilityProber(
            engines=[paddle_engine],
            interval_s=settings.model_probe_interval_s,
        )
        model_prober.start()

    return AppState(
        settings=settings,
        metrics=metrics,
        persistence=persistence,
        model_registry=model_registry,
        job_manager=job_manager,
        idempotency=idempotency,
        scanner=scanner,
        router=router,
        pipeline=pipeline,
        log_buffer=log_buffer,
        model_prober=model_prober,
        engine_gate=EngineRequestGate(),
        server_registry=server_registry,
        dispatch=dispatch,
    )
