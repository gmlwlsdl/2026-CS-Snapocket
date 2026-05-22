"""Graph hierarchy API owned by the AI service."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import get_state, require_api_key
from app.api.utils import ok_response
from app.services.graph_hierarchy import (
    EmbeddedGraphDocument,
    GraphDocument,
    GraphLinkSettings,
    build_graph_context,
    build_graph_text,
    build_links,
    estimate_generality,
    graph_role_anchor_texts,
    split_graph_chunks,
)
from app.services.semantic_search import SemanticSearchUnavailable
from app.services.state import AppState

router = APIRouter(prefix="/v1/graph", tags=["graph-hierarchy"])


def _vector_cosine(source: tuple[float, ...], target: tuple[float, ...]) -> float:
    if not source or not target or len(source) != len(target):
        return 0.0
    source_norm = math.sqrt(sum(value * value for value in source))
    target_norm = math.sqrt(sum(value * value for value in target))
    if source_norm == 0.0 or target_norm == 0.0:
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(source, target)) / (source_norm * target_norm)))


def _estimate_corpus_centrality(context_vector_by_id: dict[str, tuple[float, ...]]) -> dict[str, float]:
    raw_scores: dict[str, float] = {}
    items = list(context_vector_by_id.items())
    for source_id, source_vector in items:
        scores = [
            _vector_cosine(source_vector, target_vector)
            for target_id, target_vector in items
            if target_id != source_id
        ]
        if not scores:
            raw_scores[source_id] = 0.5
            continue
        top_scores = sorted(scores, reverse=True)[: min(5, len(scores))]
        raw_scores[source_id] = sum(top_scores) / max(1, len(top_scores))

    if not raw_scores:
        return {}
    low = min(raw_scores.values())
    high = max(raw_scores.values())
    if high <= low:
        return {document_id: 0.5 for document_id in raw_scores}
    return {
        document_id: round(0.42 + (0.20 * ((score - low) / (high - low))), 4)
        for document_id, score in raw_scores.items()
    }


def _parent_rerank_query(parent_context: str) -> str:
    return (
        "이 문서가 설명하는 상위 개념, 분야, 방법, 원리의 구체 사례나 하위 주제인지 판단한다. "
        f"상위 문서: {parent_context}"
    )


def _reranker_scores_for_candidates(
    *,
    service,
    source_document: GraphDocument,
    candidate_documents: list[GraphDocument],
) -> dict[str, dict[str, float | None]]:
    if not hasattr(service, "rerank_pairs") or not candidate_documents:
        return {}

    source_context = build_graph_context(source_document)
    candidate_contexts = [build_graph_context(document) for document in candidate_documents]
    pairs: list[tuple[str, str]] = []
    refs: list[tuple[str, str]] = []
    for candidate, candidate_context in zip(candidate_documents, candidate_contexts):
        candidate_id = candidate.document_id
        pairs.extend(
            [
                (source_context, candidate_context),
                (_parent_rerank_query(source_context), candidate_context),
                (_parent_rerank_query(candidate_context), source_context),
            ]
        )
        refs.extend(
            [
                (candidate_id, "related"),
                (candidate_id, "source_parent"),
                (candidate_id, "target_parent"),
            ]
        )

    scores = service.rerank_pairs(pairs)
    by_id: dict[str, dict[str, float | None]] = {}
    for (candidate_id, key), score in zip(refs, scores):
        by_id.setdefault(candidate_id, {})[key] = score
    return by_id


class GraphDocumentPayload(BaseModel):
    document_id: str = Field(min_length=1)
    title: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    raw_text: str | None = None
    updated_at: str | None = None


class GraphLinkRequest(BaseModel):
    user_id: str = Field(min_length=1)
    source_document: GraphDocumentPayload
    candidate_documents: list[GraphDocumentPayload] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=50)
    max_edges: int | None = Field(default=None, ge=1, le=20)
    min_parent_score: float | None = Field(default=None, ge=0.0, le=1.0)
    min_similar_score: float | None = Field(default=None, ge=0.0, le=1.0)
    parent_margin: float | None = Field(default=None, ge=0.0, le=1.0)


class GraphBatchLinkRequest(BaseModel):
    user_id: str = Field(min_length=1)
    documents: list[GraphDocumentPayload] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=50)
    max_edges: int | None = Field(default=None, ge=1, le=20)
    min_parent_score: float | None = Field(default=None, ge=0.0, le=1.0)
    min_similar_score: float | None = Field(default=None, ge=0.0, le=1.0)
    parent_margin: float | None = Field(default=None, ge=0.0, le=1.0)


def _to_graph_document(payload: GraphDocumentPayload) -> GraphDocument:
    return GraphDocument(
        document_id=str(payload.document_id),
        title=str(payload.title or ""),
        category=str(payload.category or ""),
        tags=tuple(str(tag) for tag in payload.tags if str(tag).strip()),
        summary=str(payload.summary or ""),
        raw_text=str(payload.raw_text or ""),
        updated_at=str(payload.updated_at or ""),
    )


def _settings_from_request(payload: GraphLinkRequest, state: AppState) -> GraphLinkSettings:
    settings = state.settings
    return GraphLinkSettings(
        max_top_k=int(payload.limit if payload.limit is not None else getattr(settings, "graph_max_top_k", 8)),
        max_edges_per_doc=int(
            payload.max_edges if payload.max_edges is not None else getattr(settings, "graph_max_edges_per_doc", 3)
        ),
        min_parent_score=float(
            payload.min_parent_score
            if payload.min_parent_score is not None
            else getattr(settings, "graph_min_parent_score", 0.33)
        ),
        min_similar_score=float(
            payload.min_similar_score
            if payload.min_similar_score is not None
            else getattr(settings, "graph_min_similar_score", 0.55)
        ),
        parent_margin=float(
            payload.parent_margin if payload.parent_margin is not None else getattr(settings, "graph_parent_margin", 0.02)
        ),
        min_generality_delta=float(getattr(settings, "graph_min_generality_delta", 0.015)),
        min_parent_generality=float(getattr(settings, "graph_min_parent_generality", 0.46)),
        min_parent_topic_alignment=float(getattr(settings, "graph_min_parent_topic_alignment", 0.59)),
        ambiguous_parent_margin=float(getattr(settings, "graph_ambiguous_parent_margin", 0.045)),
        max_rerank_candidates=int(getattr(settings, "graph_max_rerank_candidates", 12)),
    )


def _embed_documents(
    documents: list[GraphDocument],
    settings: GraphLinkSettings,
    service,
) -> dict[str, EmbeddedGraphDocument]:
    chunks_by_id: dict[str, list[str]] = {}
    for document in documents:
        if hasattr(service, "chunk_text"):
            chunks = service.chunk_text(
                document.raw_text,
                max_chunks=settings.max_chunks_per_doc,
                target_tokens=settings.graph_chunk_target_tokens,
                overlap_tokens=settings.graph_chunk_overlap_tokens,
            )
        else:
            chunks = split_graph_chunks(document, settings)
        chunks_by_id[document.document_id] = chunks
    flat_chunks: list[str] = []
    flat_refs: list[tuple[str, int]] = []
    for document_id, chunks in chunks_by_id.items():
        for index, chunk in enumerate(chunks):
            flat_refs.append((document_id, index))
            flat_chunks.append(chunk)

    context_refs = [document.document_id for document in documents]
    context_texts = [build_graph_context(document) for document in documents]
    sparse_vectors = (
        service.sparse_token_vectors(context_texts)
        if hasattr(service, "sparse_token_vectors")
        else [{} for _document in documents]
    )
    anchor_texts = graph_role_anchor_texts()
    vectors = service.encode_texts([*flat_chunks, *context_texts, *anchor_texts])
    chunk_vectors = vectors[: len(flat_chunks)]
    context_vectors = vectors[len(flat_chunks) : len(flat_chunks) + len(context_texts)]
    anchor_vectors = tuple(
        tuple(float(value) for value in vector)
        for vector in vectors[len(flat_chunks) + len(context_texts) :]
    )
    vectors_by_id: dict[str, list[tuple[float, ...]]] = {document.document_id: [] for document in documents}
    for (document_id, _index), vector in zip(flat_refs, chunk_vectors):
        vectors_by_id[document_id].append(tuple(float(value) for value in vector))
    context_vector_by_id = {
        document_id: tuple(float(value) for value in vector)
        for document_id, vector in zip(context_refs, context_vectors)
    }
    centrality_by_id = _estimate_corpus_centrality(context_vector_by_id)
    sparse_vector_by_id = {
        document_id: {
            int(token_id): float(weight)
            for token_id, weight in sparse_vector.items()
        }
        for document_id, sparse_vector in zip(context_refs, sparse_vectors)
    }

    documents_by_id = {document.document_id: document for document in documents}
    embedded: dict[str, EmbeddedGraphDocument] = {}
    for document_id, chunks in chunks_by_id.items():
        anchor_generality = estimate_generality(
            tuple([context_vector_by_id.get(document_id, ()), *vectors_by_id.get(document_id, [])]),
            anchor_vectors,
        )
        centrality = centrality_by_id.get(document_id, 0.5)
        generality = round((0.58 * anchor_generality) + (0.42 * centrality), 4)
        embedded[document_id] = EmbeddedGraphDocument(
            document=documents_by_id[document_id],
            chunks=tuple(chunks),
            vectors=tuple(vectors_by_id.get(document_id, [])),
            context_vector=context_vector_by_id.get(document_id, ()),
            sparse_vector=sparse_vector_by_id.get(document_id, {}),
            centrality=centrality,
            generality=generality,
        )
    return embedded


def _select_reranker_documents(
    *,
    source_embedded: EmbeddedGraphDocument,
    candidate_documents: list[GraphDocument],
    embedded_by_id: dict[str, EmbeddedGraphDocument],
    settings: GraphLinkSettings,
) -> list[GraphDocument]:
    ranked: list[tuple[float, GraphDocument]] = []
    for document in candidate_documents:
        embedded = embedded_by_id.get(document.document_id)
        if embedded is None:
            continue
        ranked.append((_vector_cosine(source_embedded.context_vector, embedded.context_vector), document))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [document for _score, document in ranked[: max(0, settings.max_rerank_candidates)]]


@router.post("/link", dependencies=[Depends(require_api_key)])
def link_graph_documents(
    request: Request,
    payload: GraphLinkRequest,
    state: AppState = Depends(get_state),
):
    source_document = _to_graph_document(payload.source_document)
    candidate_documents_all = [_to_graph_document(item) for item in payload.candidate_documents]
    settings = _settings_from_request(payload, state)

    semantic_available = False
    semantic_scores_by_id: dict[str, float] = {}
    service = getattr(state, "semantic_search", None)
    if service is None:
        return ok_response(
            request,
            {
                "items": [],
                "semantic_available": False,
                "candidates_considered": len(candidate_documents_all),
                "skipped_reason": "semantic embedding service is unavailable",
            },
        )

    try:
        semantic_items = service.search(
            query=build_graph_text(source_document),
            user_id=payload.user_id,
            limit=settings.max_top_k,
        )
        semantic_scores_by_id = {
            str(item.get("document_id") or ""): float(item.get("score") or 0.0)
            for item in semantic_items
            if str(item.get("document_id") or "").strip()
        }
    except SemanticSearchUnavailable:
        semantic_scores_by_id = {}

    if semantic_scores_by_id:
        candidate_documents = [
            document
            for document in candidate_documents_all
            if document.document_id in semantic_scores_by_id
        ]
        candidate_documents.sort(
            key=lambda document: semantic_scores_by_id.get(document.document_id, 0.0),
            reverse=True,
        )
    else:
        candidate_documents = candidate_documents_all[: settings.max_top_k]

    candidate_documents = candidate_documents[: settings.max_top_k]

    try:
        embedded_by_id = _embed_documents([source_document, *candidate_documents], settings, service)
        semantic_available = True
    except SemanticSearchUnavailable as exc:
        return ok_response(
            request,
            {
                "items": [],
                "semantic_available": False,
                "candidates_considered": len(candidate_documents_all),
                "candidates_embedded": len(candidate_documents),
                "skipped_reason": str(exc),
            },
        )

    source_embedded = embedded_by_id.get(source_document.document_id)
    candidate_embedded = [
        embedded_by_id[item.document_id]
        for item in candidate_documents
        if item.document_id in embedded_by_id
    ]
    if source_embedded is None:
        items = []
    else:
        reranker_scores_by_id = _reranker_scores_for_candidates(
            service=service,
            source_document=source_document,
            candidate_documents=_select_reranker_documents(
                source_embedded=source_embedded,
                candidate_documents=candidate_documents,
                embedded_by_id=embedded_by_id,
                settings=settings,
            ),
        )
        items = build_links(
            source_document=source_embedded,
            candidate_documents=candidate_embedded,
            semantic_scores_by_id=semantic_scores_by_id,
            settings=settings,
            reranker_scores_by_id=reranker_scores_by_id,
        )

    return ok_response(
        request,
        {
            "items": items,
            "semantic_available": semantic_available,
            "candidates_considered": len(candidate_documents_all),
            "candidates_embedded": len(candidate_documents),
        },
    )


@router.post("/link/batch", dependencies=[Depends(require_api_key)])
def link_graph_documents_batch(
    request: Request,
    payload: GraphBatchLinkRequest,
    state: AppState = Depends(get_state),
):
    documents = [_to_graph_document(item) for item in payload.documents]
    settings = _settings_from_request(payload, state)

    service = getattr(state, "semantic_search", None)
    if service is None:
        return ok_response(
            request,
            {
                "items": [],
                "semantic_available": False,
                "documents_considered": len(documents),
                "skipped_reason": "semantic embedding service is unavailable",
            },
        )

    try:
        embedded_by_id = _embed_documents(documents, settings, service)
    except SemanticSearchUnavailable as exc:
        return ok_response(
            request,
            {
                "items": [],
                "semantic_available": False,
                "documents_considered": len(documents),
                "skipped_reason": str(exc),
            },
        )

    items: list[dict] = []
    for source_document in documents:
        source_embedded = embedded_by_id.get(source_document.document_id)
        if source_embedded is None:
            continue

        candidate_embedded = [
            embedded
            for document_id, embedded in embedded_by_id.items()
            if document_id != source_document.document_id
        ]
        candidate_documents = [
            document
            for document in documents
            if document.document_id != source_document.document_id
        ]
        reranker_scores_by_id = _reranker_scores_for_candidates(
            service=service,
            source_document=source_document,
            candidate_documents=_select_reranker_documents(
                source_embedded=source_embedded,
                candidate_documents=candidate_documents,
                embedded_by_id=embedded_by_id,
                settings=settings,
            ),
        )
        items.extend(
            build_links(
                source_document=source_embedded,
                candidate_documents=candidate_embedded,
                semantic_scores_by_id={},
                settings=settings,
                reranker_scores_by_id=reranker_scores_by_id,
            )
        )

    return ok_response(
        request,
        {
            "items": items,
            "semantic_available": True,
            "documents_considered": len(documents),
        },
    )
