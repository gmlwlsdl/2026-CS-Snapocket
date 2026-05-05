"""이 파일은 AI 검색의 핵심 서비스 계층이다.

- 임베딩 모델 로딩
- Qdrant 컬렉션 생성/검증
- 문서 벡터 upsert/delete
- 사용자 범위 semantic search
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sentence_transformers import SentenceTransformer

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SemanticDocument:
    # 검색 인덱스에 올릴 최소 문서 정보만 분리한 값 객체
    document_id: str
    user_id: str
    updated_at: str
    raw_text: str


@dataclass(frozen=True)
class SemanticChunk:
    document_id: str
    user_id: str
    updated_at: str
    chunk_id: str
    chunk_index: int
    page_no: int
    section: str
    offset_start: int
    offset_end: int
    content_hash: str
    text: str


class SemanticSearchUnavailable(RuntimeError):
    pass


_SCHEMA_VERSION = "chunk-v2"
_CHUNK_TARGET_CHARS = 900
_CHUNK_OVERLAP_CHARS = 140
_CHUNK_TARGET_TOKENS = 360
_CHUNK_OVERLAP_TOKENS = 48
_METADATA_PREAMBLE_RE = re.compile(
    r"^\s*Source:\s*.+?\s+Title:\s*.+?\s+Category:\s*\S+\s+",
    re.IGNORECASE | re.DOTALL,
)
_PAYLOAD_INDEX_FIELDS = ("user_id", "document_id", "updated_at", "content_hash")


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def _strip_metadata_preamble(value: str) -> str:
    return _METADATA_PREAMBLE_RE.sub("", value, count=1).strip()


def _normalize_text(value: str | None, max_chars: int) -> str:
    # 공백만 있는 텍스트는 버리고, 너무 긴 본문은 설정 길이만큼만 사용한다.
    token = _strip_metadata_preamble(str(value or "").strip())
    token = re.sub(r"\s+", " ", token).strip()
    if not token:
        return ""
    return token[:max_chars].strip()


def _split_fixed_windows_with_offsets(text: str, *, target_chars: int, overlap_chars: int) -> list[tuple[str, int, int]]:
    """Fallback chunker that has no language-specific token or sentence rules."""

    stripped = text.strip()
    if not stripped:
        return []

    windows: list[tuple[str, int, int]] = []
    start = 0
    text_len = len(text)
    step = max(1, target_chars - max(0, overlap_chars))
    while start < text_len:
        end = min(text_len, start + target_chars)
        chunk = text[start:end].strip()
        if chunk:
            leading_ws = len(text[start:end]) - len(text[start:end].lstrip())
            trailing_ws = len(text[start:end]) - len(text[start:end].rstrip())
            windows.append((chunk, start + leading_ws, end - trailing_ws))
        if end >= text_len:
            break
        start += step
    return windows


def _split_model_token_windows_with_offsets(
    text: str,
    *,
    tokenizer: Any | None,
    target_tokens: int,
    overlap_tokens: int,
) -> list[tuple[str, int, int]]:
    """Chunk by the embedding model's own tokenizer when offset mapping is available.

    This is intentionally not a linguistic parser: no stopwords, no definition
    patterns, no English/Korean/Japanese/Chinese-specific sentence heuristics.
    The same model that embeds the text decides the token boundaries.
    """

    if tokenizer is None:
        return []
    try:
        encoded = tokenizer(
            text,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=False,
        )
    except Exception:
        return []

    input_ids = encoded.get("input_ids") if hasattr(encoded, "get") else None
    offsets = encoded.get("offset_mapping") if hasattr(encoded, "get") else None
    if not isinstance(input_ids, list) or not isinstance(offsets, list) or not input_ids or len(input_ids) != len(offsets):
        return []

    windows: list[tuple[str, int, int]] = []
    token_count = len(input_ids)
    step = max(1, target_tokens - max(0, overlap_tokens))
    start_token = 0
    while start_token < token_count:
        end_token = min(token_count, start_token + max(1, target_tokens))
        span_offsets = [
            (int(start), int(end))
            for start, end in offsets[start_token:end_token]
            if isinstance(start, int) and isinstance(end, int) and end > start
        ]
        if span_offsets:
            start = min(start for start, _end in span_offsets)
            end = max(end for _start, end in span_offsets)
            chunk = text[start:end].strip()
            if chunk:
                leading_ws = len(text[start:end]) - len(text[start:end].lstrip())
                trailing_ws = len(text[start:end]) - len(text[start:end].rstrip())
                windows.append((chunk, start + leading_ws, end - trailing_ws))
        if end_token >= token_count:
            break
        start_token += step
    return windows


def _split_document_chunks(document: SemanticDocument, max_chars: int, tokenizer: Any | None = None) -> list[SemanticChunk]:
    normalized = _normalize_text(document.raw_text, max_chars)
    if not normalized:
        return []

    content_hash = _stable_hash(normalized)
    windows = _split_model_token_windows_with_offsets(
        normalized,
        tokenizer=tokenizer,
        target_tokens=_CHUNK_TARGET_TOKENS,
        overlap_tokens=_CHUNK_OVERLAP_TOKENS,
    )
    if not windows:
        windows = _split_fixed_windows_with_offsets(
            normalized,
            target_chars=_CHUNK_TARGET_CHARS,
            overlap_chars=_CHUNK_OVERLAP_CHARS,
        )

    chunks: list[SemanticChunk] = []
    for text, start, end in windows:
        index = len(chunks)
        chunks.append(
            SemanticChunk(
                document_id=document.document_id,
                user_id=document.user_id,
                updated_at=document.updated_at,
                chunk_id=f"{document.document_id}:chunk:{index:04d}",
                chunk_index=index,
                page_no=1,
                section="body",
                offset_start=start,
                offset_end=end,
                content_hash=content_hash,
                text=text,
            )
        )
    return chunks


def _collection_vector_size(collection_info: Any) -> int | None:
    # 이미 존재하는 컬렉션의 벡터 차원을 읽어 현재 모델 차원과 맞는지 비교한다.
    config = getattr(collection_info, "config", None)
    params = getattr(config, "params", None)
    vectors = getattr(params, "vectors", None)
    size = getattr(vectors, "size", None)
    return int(size) if isinstance(size, int) else None


class SemanticSearchService:
    def __init__(self, settings: Settings):
        # 설정값을 보관하고, enabled 상태면 시작 시점에 바로 모델/Qdrant 초기화를 시도한다.
        self._settings = settings
        self._enabled = bool(settings.semantic_search_enable)
        self._model_ref = self._resolve_model_ref(settings.semantic_embedding_model)
        self._collection_name = settings.semantic_qdrant_collection
        self._qdrant_url = settings.semantic_qdrant_url
        self._max_chars = max(256, int(settings.semantic_raw_text_max_chars))
        self._model: SentenceTransformer | None = None
        self._client: QdrantClient | None = None
        self._embedding_dim: int | None = None
        self._last_error: str | None = None

        if self._enabled:
            try:
                self._initialize()
            except Exception as exc:  # pragma: no cover - runtime-dependent
                self._last_error = str(exc)
                logger.exception("Semantic search initialization failed: %s", exc)

    @property
    def model_ref(self) -> str:
        return self._model_ref

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def available(self) -> bool:
        return (
            self._enabled
            and self._client is not None
            and self._model is not None
            and self._embedding_dim is not None
        )

    def availability_detail(self) -> dict[str, Any]:
        # 상태 API에서 그대로 노출할 수 있는 최소 진단 정보
        return {
            "enabled": self._enabled,
            "available": self.available(),
            "schema_version": _SCHEMA_VERSION,
            "model_ref": self._model_ref,
            "collection": self._collection_name,
            "qdrant_url": self._qdrant_url,
            "embedding_dim": self._embedding_dim,
            "chunk_target_tokens": _CHUNK_TARGET_TOKENS,
            "chunk_overlap_tokens": _CHUNK_OVERLAP_TOKENS,
            "fallback_chunk_target_chars": _CHUNK_TARGET_CHARS,
            "fallback_chunk_overlap_chars": _CHUNK_OVERLAP_CHARS,
            "error": self._last_error,
        }

    def _resolve_model_ref(self, configured: str) -> str:
        # 로컬에 다운로드한 모델이 있으면 그 경로를 우선 사용하고,
        # 없으면 환경변수 또는 HF 모델 식별자를 그대로 사용한다.
        token = str(configured or "").strip()
        if not token:
            token = "dragonkue/BGE-m3-ko"

        resolved_file = Path(__file__).resolve()
        ai_root: Path | None = None
        for parent in resolved_file.parents:
            if (parent / "model").is_dir():
                ai_root = parent
                break
        if ai_root is None:
            cwd = Path.cwd().resolve()
            ai_root = cwd if (cwd / "model").is_dir() else resolved_file.parents[2]

        local_candidates = [
            ai_root / "model" / "BGE-m3-ko",
            ai_root / "model" / token,
        ]
        for candidate in local_candidates:
            if candidate.is_dir() and (candidate / "config.json").exists():
                return str(candidate.resolve())

        candidate_path = Path(token)
        if candidate_path.is_dir() and (candidate_path / "config.json").exists():
            return str(candidate_path.resolve())
        return token

    def _initialize(self) -> None:
        # 로컬에 내려받은 모델이 있으면 그 경로를 우선 사용하고, 없으면 HF 식별자를 그대로 쓴다.
        self._model = SentenceTransformer(self._model_ref)
        self._client = QdrantClient(url=self._qdrant_url, timeout=self._settings.semantic_qdrant_timeout_s)
        # probe 벡터 1개를 만들어 모델의 실제 출력 차원을 확인한다.
        probe = self._model.encode(["semantic-search-probe"], normalize_embeddings=True)
        self._embedding_dim = len(probe[0])
        self._ensure_collection()
        self._last_error = None

    def _ensure_available(self) -> None:
        # 모델, Qdrant client, 벡터 차원이 모두 준비되어야 검색 서비스를 사용할 수 있다.
        if not self.available():
            raise SemanticSearchUnavailable(self._last_error or "semantic search service is unavailable")

    def _ensure_collection(self) -> None:
        # 컬렉션이 없으면 생성하고, 있으면 현재 모델 차원과 충돌이 없는지만 확인한다.
        self._ensure_available()
        assert self._client is not None
        assert self._embedding_dim is not None
        collections = {item.name for item in self._client.get_collections().collections}
        if self._collection_name in collections:
            collection_info = self._client.get_collection(self._collection_name)
            existing_size = _collection_vector_size(collection_info)
            if existing_size is not None and existing_size != self._embedding_dim:
                raise SemanticSearchUnavailable(
                    f"Qdrant collection vector size mismatch: expected {self._embedding_dim}, got {existing_size}"
                )
            self._ensure_payload_indexes()
            return
        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=self._embedding_dim,
                distance=qdrant_models.Distance.COSINE,
            ),
        )
        self._ensure_payload_indexes()

    def _ensure_payload_indexes(self) -> None:
        assert self._client is not None
        for field_name in _PAYLOAD_INDEX_FIELDS:
            try:
                self._client.create_payload_index(
                    collection_name=self._collection_name,
                    field_name=field_name,
                    field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
                    wait=True,
                )
            except Exception as exc:  # Qdrant returns an error if an index already exists on some versions.
                logger.debug("Payload index ensure skipped for %s: %s", field_name, exc)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        # 문서 본문이나 검색 질의를 모두 동일한 임베딩 모델로 벡터화한다.
        self._ensure_available()
        assert self._model is not None
        vectors = self._model.encode(
            texts,
            batch_size=max(1, min(16, len(texts))),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def _tokenizer(self) -> Any | None:
        model = self._model
        return getattr(model, "tokenizer", None) if model is not None else None

    def chunk_text(self, text: str, *, max_chunks: int, max_chars: int | None = None) -> list[str]:
        """Expose model-token chunking to graph scoring without duplicating rules."""

        normalized = _normalize_text(text, max_chars or self._max_chars)
        if not normalized:
            return []
        windows = _split_model_token_windows_with_offsets(
            normalized,
            tokenizer=self._tokenizer(),
            target_tokens=_CHUNK_TARGET_TOKENS,
            overlap_tokens=_CHUNK_OVERLAP_TOKENS,
        )
        if not windows:
            windows = _split_fixed_windows_with_offsets(
                normalized,
                target_chars=_CHUNK_TARGET_CHARS,
                overlap_chars=_CHUNK_OVERLAP_CHARS,
            )
        return [chunk for chunk, _start, _end in windows[: max(1, max_chunks)]]

    def sparse_token_vectors(self, texts: list[str], *, max_chars: int | None = None) -> list[dict[int, float]]:
        """Build language-agnostic sparse evidence from the embedding tokenizer.

        This is not a hand-written parser: token boundaries come from the same
        multilingual model tokenizer used for dense embeddings, and corpus IDF
        is computed only from the active document set being compared.
        """

        tokenizer = self._tokenizer()
        if tokenizer is None:
            return [{} for _text in texts]

        prepared = [_normalize_text(text, max_chars or self._max_chars) for text in texts]
        special_ids = {int(token_id) for token_id in getattr(tokenizer, "all_special_ids", [])}
        counters: list[Counter[int]] = []
        document_frequency: Counter[int] = Counter()
        for text in prepared:
            if not text:
                counters.append(Counter())
                continue
            try:
                encoded = tokenizer(text, add_special_tokens=False, truncation=False)
                input_ids = encoded.get("input_ids") if hasattr(encoded, "get") else []
            except Exception:
                input_ids = []
            counter = Counter(
                int(token_id)
                for token_id in input_ids
                if isinstance(token_id, int) and int(token_id) not in special_ids
            )
            counters.append(counter)
            document_frequency.update(counter.keys())

        doc_count = max(1, len([counter for counter in counters if counter]))
        vectors: list[dict[int, float]] = []
        for counter in counters:
            if not counter:
                vectors.append({})
                continue
            weights: dict[int, float] = {}
            for token_id, term_frequency in counter.items():
                idf = math.log((doc_count + 1.0) / (float(document_frequency.get(token_id, 0)) + 0.5))
                if idf <= 0.0:
                    continue
                weights[token_id] = (1.0 + math.log(float(term_frequency))) * idf
            vectors.append(weights)
        return vectors

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        # Graph hierarchy는 Qdrant 조회가 아니라 chunk coverage 계산에 임베딩만 필요하다.
        # 따라서 Qdrant가 잠깐 불안정해도 모델이 로드되어 있으면 임베딩을 제공한다.
        if not self._enabled or self._model is None:
            raise SemanticSearchUnavailable(self._last_error or "semantic embedding model is unavailable")

        prepared = [_normalize_text(item, self._max_chars) for item in texts]
        indexed_texts = [(index, item) for index, item in enumerate(prepared) if item]
        if not indexed_texts:
            vector_size = int(self._embedding_dim or 0)
            return [[0.0] * vector_size for _item in texts] if vector_size > 0 else []

        encoded = self._model.encode(
            [item for _index, item in indexed_texts],
            batch_size=max(1, min(16, len(indexed_texts))),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        vector_size = len(encoded[0]) if len(encoded) > 0 else int(self._embedding_dim or 0)
        vectors: list[list[float]] = [[0.0] * vector_size for _item in texts]
        for (index, _item), vector in zip(indexed_texts, encoded):
            vectors[index] = vector.tolist()
        return vectors

    def _chunk_to_point(self, chunk: SemanticChunk, vector: list[float]) -> qdrant_models.PointStruct:
        # Qdrant point id는 UUID/정수만 허용하므로 user_id+document_id+chunk_id 조합을 안정 UUID로 변환한다.
        point_id = str(uuid5(NAMESPACE_URL, f"{chunk.user_id}:{chunk.document_id}:{chunk.chunk_id}"))
        return qdrant_models.PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "schema_version": _SCHEMA_VERSION,
                "document_id": chunk.document_id,
                "user_id": chunk.user_id,
                "updated_at": chunk.updated_at,
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "page_no": chunk.page_no,
                "section": chunk.section,
                "offset_start": chunk.offset_start,
                "offset_end": chunk.offset_end,
                "content_hash": chunk.content_hash,
                "chunk_text": chunk.text[:1200],
            },
        )

    def upsert_documents(self, documents: list[SemanticDocument]) -> dict[str, int]:
        # 빈 raw_text 문서는 임베딩 품질이 없으므로 검색 인덱스에서 제외한다.
        prepared_documents = [
            SemanticDocument(
                document_id=item.document_id,
                user_id=item.user_id,
                updated_at=item.updated_at,
                raw_text=_normalize_text(item.raw_text, self._max_chars),
            )
            for item in documents
            if str(item.document_id).strip() and _normalize_text(item.raw_text, self._max_chars)
        ]
        if not prepared_documents:
            return {"upserted": 0, "chunks_upserted": 0}

        self._ensure_available()
        assert self._client is not None

        # 같은 document_id의 이전 chunk가 남지 않도록 문서 단위 삭제 후 chunk point를 새로 넣는다.
        user_ids = {item.user_id for item in prepared_documents}
        for user_id in user_ids:
            doc_ids = [item.document_id for item in prepared_documents if item.user_id == user_id]
            self.delete_documents(doc_ids, user_id=user_id)

        chunks = [
            chunk
            for document in prepared_documents
            for chunk in _split_document_chunks(document, self._max_chars, tokenizer=self._tokenizer())
        ]
        if not chunks:
            return {"upserted": 0, "chunks_upserted": 0}

        vectors = self._encode([item.text for item in chunks])
        points = [self._chunk_to_point(item, vector) for item, vector in zip(chunks, vectors)]
        self._client.upsert(collection_name=self._collection_name, points=points, wait=True)
        return {"upserted": len(prepared_documents), "chunks_upserted": len(points)}

    def delete_documents(self, document_ids: list[str], *, user_id: str | None = None) -> dict[str, int]:
        # 문서 id가 비어 있으면 Qdrant 호출 없이 바로 종료한다.
        doc_ids = [str(item).strip() for item in document_ids if str(item).strip()]
        if not doc_ids:
            return {"deleted": 0}

        self._ensure_available()
        assert self._client is not None

        # 삭제는 point id 대신 payload(document_id, user_id) 기준으로 수행해
        # 백엔드가 point id 생성 규칙을 몰라도 안전하게 동작하게 만든다.
        match_any = qdrant_models.MatchAny(any=doc_ids)
        conditions: list[qdrant_models.Condition] = [
            qdrant_models.FieldCondition(
                key="document_id",
                match=match_any,
            )
        ]
        if user_id:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="user_id",
                    match=qdrant_models.MatchValue(value=user_id),
                )
            )

        self._client.delete(
            collection_name=self._collection_name,
            points_selector=qdrant_models.FilterSelector(
                filter=qdrant_models.Filter(must=conditions)
            ),
            wait=True,
        )
        return {"deleted": len(doc_ids)}

    def search(self, *, query: str, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        # 빈 질의는 검색하지 않는다.
        token = str(query or "").strip()
        if not token:
            return []

        self._ensure_available()
        assert self._client is not None

        # retrieve_candidates -> fuse -> rerank -> aggregate_by_document.
        vector = self._encode([token])[0]
        candidate_limit = max(10, min(200, limit * 8))
        points = self._client.search(
            collection_name=self._collection_name,
            query_vector=vector,
            # 다른 사용자의 문서가 섞이지 않도록 user_id 기준 filter를 항상 건다.
            query_filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="user_id",
                        match=qdrant_models.MatchValue(value=user_id),
                    )
                ]
            ),
            with_payload=True,
            limit=candidate_limit,
        )

        by_document: dict[str, dict[str, Any]] = {}
        for rank, point in enumerate(points, start=1):
            payload = point.payload or {}
            document_id = str(payload.get("document_id") or point.id)
            chunk_text = str(payload.get("chunk_text") or "")
            dense_score = float(point.score)
            reciprocal_rank = 1.0 / (60.0 + rank)
            rerank_score = round((0.96 * dense_score) + (0.04 * reciprocal_rank), 4)
            final_score = rerank_score

            candidate = {
                "document_id": document_id,
                "score": final_score,
                "updated_at": str(payload.get("updated_at") or ""),
                "reason": {
                    "schema_version": _SCHEMA_VERSION,
                    "dense_score": round(dense_score, 4),
                    "sparse_score": None,
                    "rerank_score": rerank_score,
                    "final_score": final_score,
                    "chunk_id": str(payload.get("chunk_id") or ""),
                    "chunk_index": int(payload.get("chunk_index") or 0),
                    "page_no": int(payload.get("page_no") or 1),
                    "section": str(payload.get("section") or "body"),
                    "offset_start": int(payload.get("offset_start") or 0),
                    "offset_end": int(payload.get("offset_end") or 0),
                    "content_hash": str(payload.get("content_hash") or ""),
                    "snippet": chunk_text[:240],
                    "retrieval_pipeline": "dense_chunk_rrf_aggregate",
                },
            }
            existing = by_document.get(document_id)
            if existing is None or float(candidate["score"]) > float(existing["score"]):
                by_document[document_id] = candidate

        results = sorted(by_document.values(), key=lambda item: float(item.get("score") or 0.0), reverse=True)
        return results[: max(1, min(limit, 50))]

    def list_documents(self, *, user_id: str, batch_size: int = 256) -> list[dict[str, Any]]:
        # 사용자별로 현재 Qdrant에 들어 있는 문서 메타데이터를 전부 조회한다.
        self._ensure_available()
        assert self._client is not None

        by_document: dict[str, dict[str, Any]] = {}
        next_offset: Any = None
        while True:
            points, next_offset = self._client.scroll(
                collection_name=self._collection_name,
                scroll_filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="user_id",
                            match=qdrant_models.MatchValue(value=user_id),
                        )
                    ]
                ),
                with_payload=True,
                with_vectors=False,
                limit=max(1, min(batch_size, 1000)),
                offset=next_offset,
            )
            for point in points:
                payload = point.payload or {}
                document_id = str(payload.get("document_id") or point.id)
                if not document_id:
                    continue
                item = by_document.setdefault(
                    document_id,
                    {
                        "document_id": document_id,
                        "updated_at": str(payload.get("updated_at") or ""),
                        "content_hash": str(payload.get("content_hash") or ""),
                        "chunk_count": 0,
                        "schema_version": str(payload.get("schema_version") or _SCHEMA_VERSION),
                    },
                )
                item["chunk_count"] = int(item.get("chunk_count") or 0) + 1
            if next_offset is None:
                break
        return list(by_document.values())

    def sync_documents(
        self,
        *,
        documents: list[SemanticDocument],
        deleted_document_ids: list[str] | None = None,
        user_id: str | None = None,
    ) -> dict[str, int]:
        # 동기화는 "유효 문서 upsert + 비어 있는 문서/삭제 문서 delete" 두 단계로 처리한다.
        deleted_document_ids = deleted_document_ids or []
        # raw_text가 비어 있는 문서는 검색 인덱스에 남길 이유가 없어서 삭제 대상으로 함께 묶는다.
        blank_text_doc_ids = [
            item.document_id
            for item in documents
            if item.document_id and not _normalize_text(item.raw_text, self._max_chars)
        ]
        upsert_result = self.upsert_documents(documents)
        delete_result = self.delete_documents(
            list({*deleted_document_ids, *blank_text_doc_ids}),
            user_id=user_id,
        )
        return {
            "upserted": int(upsert_result.get("upserted", 0)),
            "chunks_upserted": int(upsert_result.get("chunks_upserted", 0)),
            "deleted": int(delete_result.get("deleted", 0)),
        }
