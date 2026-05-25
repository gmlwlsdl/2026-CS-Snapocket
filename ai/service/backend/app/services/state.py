"""이 파일은 AI 서버의 전역 상태(AppState)를 조립한다.

- 설정 로드
- OCR/ASR/큐/저장소 초기화
- semantic search 서비스 주입
- 앱 시작 시 필요한 의존성 연결
"""

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
from app.services.ocr.paddle_doc_parser_engine import PaddleOCRVLDocParserEngine
from app.services.ocr.router import OCREngineRouter
from app.services.persistence import PersistenceStore
from app.services.pipeline import InferencePipeline
from app.services.redis_queue import RedisJobManager
from app.services.security_scan import MalwareScanner
from app.services.semantic_search import SemanticSearchService
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
    qwen_asr_engine: QwenASREngine | None = None
    log_buffer: LogBuffer = None  # type: ignore[assignment]
    model_prober: ModelAvailabilityProber | None = None
    engine_gate: EngineRequestGate | None = None
    server_registry: ServerRegistry | None = None
    dispatch: DispatchService | None = None
    # 백엔드 검색 요청을 처리할 semantic search 서비스
    semantic_search: SemanticSearchService | None = None


def _is_valid_qwen_asr_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if not (path / "config.json").exists():
        return False
    has_weights = any(path.glob("model-*.safetensors"))
    return has_weights


def _resolve_qwen_asr_model_ref(settings: Settings) -> str:
    """로컬 ASR 모델 디렉터리를 우선 탐지하고, 없으면 설정값을 사용한다."""
    resolved_file = Path(__file__).resolve()

    # 실행 환경(로컬/컨테이너)마다 경로 깊이가 달라질 수 있어 고정 인덱스를 쓰지 않는다.
    ai_root: Path | None = None
    for parent in resolved_file.parents:
        if (parent / "model").is_dir():
            ai_root = parent
            break
    if ai_root is None:
        cwd = Path.cwd().resolve()
        if (cwd / "model").is_dir():
            ai_root = cwd
        elif len(resolved_file.parents) > 2:
            ai_root = resolved_file.parents[2]
        else:
            ai_root = resolved_file.parent

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

    # 기본 경로는 공식 PaddleOCRVL doc-parser pipeline이다. llama.cpp는
    # PaddleOCRVL 내부의 VLM recognition backend로만 연결한다.
    if str(settings.paddle_runtime or "").strip().lower() in {"llama", "llamacpp", "legacy"}:
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
    else:
        paddle_engine = PaddleOCRVLDocParserEngine(
            enabled=settings.paddle_enable,
            vl_rec_server_url=settings.llm_base_url,
            pipeline_version=settings.paddle_doc_parser_pipeline_version,
            device=settings.paddle_doc_parser_device,
            engine=settings.paddle_doc_parser_engine,
            request_timeout_s=settings.llm_request_timeout_s,
            availability_ttl_s=settings.model_availability_ttl_s,
            use_doc_preprocessor=settings.paddle_doc_parser_use_doc_preprocessor,
            use_layout_detection=settings.paddle_doc_parser_use_layout_detection,
            use_chart_recognition=settings.paddle_doc_parser_use_chart_recognition,
            use_seal_recognition=settings.paddle_doc_parser_use_seal_recognition,
            use_ocr_for_image_block=settings.paddle_doc_parser_use_ocr_for_image_block,
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
        dtype=settings.qwen_asr_dtype,
        device_map=settings.qwen_asr_device_map,
        low_cpu_mem_usage=settings.qwen_asr_low_cpu_mem_usage,
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
        qwen_asr_engine=qwen_asr_engine,
        request_timeout_s=settings.dispatch_upstream_timeout_s,
    )
    model_prober = None
    if settings.model_probe_enable:
        model_prober = ModelAvailabilityProber(
            engines=[paddle_engine],
            interval_s=settings.model_probe_interval_s,
        )
        model_prober.start()
    # semantic search는 앱 시작 시 함께 초기화해 readiness/status에서 바로 상태를 확인할 수 있게 한다.
    semantic_search = SemanticSearchService(settings)

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
        qwen_asr_engine=qwen_asr_engine,
        log_buffer=log_buffer,
        model_prober=model_prober,
        engine_gate=EngineRequestGate(),
        server_registry=server_registry,
        dispatch=dispatch,
        semantic_search=semantic_search,
    )
