"""이 파일은 AI 검색의 핵심 서비스 계층이다.

- 임베딩 모델 로딩
- Qdrant 컬렉션 생성/검증
- 문서 벡터 upsert/delete
- 사용자 범위 semantic search
"""

from __future__ import annotations

import logging
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


class SemanticSearchUnavailable(RuntimeError):
    pass


def _normalize_text(value: str | None, max_chars: int) -> str:
    # 공백만 있는 텍스트는 버리고, 너무 긴 본문은 설정 길이만큼만 사용한다.
    token = str(value or "").strip()
    if not token:
        return ""
    return token[:max_chars].strip()


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
            "model_ref": self._model_ref,
            "collection": self._collection_name,
            "qdrant_url": self._qdrant_url,
            "embedding_dim": self._embedding_dim,
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
            return
        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=self._embedding_dim,
                distance=qdrant_models.Distance.COSINE,
            ),
        )

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

    def _document_to_point(self, document: SemanticDocument, vector: list[float]) -> qdrant_models.PointStruct:
        # Qdrant point id는 UUID/정수만 허용하므로, user_id+document_id 조합을 안정적인 UUID로 변환한다.
        point_id = str(uuid5(NAMESPACE_URL, f"{document.user_id}:{document.document_id}"))
        return qdrant_models.PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "document_id": document.document_id,
                "user_id": document.user_id,
                "updated_at": document.updated_at,
            },
        )

    def upsert_documents(self, documents: list[SemanticDocument]) -> dict[str, int]:
        # 빈 raw_text 문서는 임베딩 품질이 없으므로 검색 인덱스에서 제외한다.
        prepared = [
            SemanticDocument(
                document_id=item.document_id,
                user_id=item.user_id,
                updated_at=item.updated_at,
                raw_text=_normalize_text(item.raw_text, self._max_chars),
            )
            for item in documents
            if str(item.document_id).strip() and _normalize_text(item.raw_text, self._max_chars)
        ]
        if not prepared:
            return {"upserted": 0}

        self._ensure_available()
        assert self._client is not None

        # 본문 벡터를 만든 뒤 payload와 함께 한 번에 upsert한다.
        vectors = self._encode([item.raw_text for item in prepared])
        points = [self._document_to_point(item, vector) for item, vector in zip(prepared, vectors)]
        self._client.upsert(collection_name=self._collection_name, points=points, wait=True)
        return {"upserted": len(points)}

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

        # 질의도 동일한 임베딩 모델로 벡터화해 사용자 범위 내에서만 검색한다.
        vector = self._encode([token])[0]
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
            limit=max(1, min(limit, 50)),
        )
        return [
            {
                # 최종 검증은 백엔드가 하므로, 여기서는 document_id/score/updated_at만 돌려준다.
                "document_id": str(point.payload.get("document_id") or point.id),
                "score": float(point.score),
                "updated_at": str(point.payload.get("updated_at") or ""),
            }
            for point in points
        ]

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
            "deleted": int(delete_result.get("deleted", 0)),
        }
