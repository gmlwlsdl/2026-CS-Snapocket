"""Graph hierarchy API owned by the AI service."""

from __future__ import annotations

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
    sparse_vector_by_id = {
        document_id: {
            int(token_id): float(weight)
            for token_id, weight in sparse_vector.items()
        }
        for document_id, sparse_vector in zip(context_refs, sparse_vectors)
    }

    documents_by_id = {document.document_id: document for document in documents}
    return {
        document_id: EmbeddedGraphDocument(
            document=documents_by_id[document_id],
            chunks=tuple(chunks),
            vectors=tuple(vectors_by_id.get(document_id, [])),
            context_vector=context_vector_by_id.get(document_id, ()),
            sparse_vector=sparse_vector_by_id.get(document_id, {}),
            generality=estimate_generality(
                tuple([context_vector_by_id.get(document_id, ()), *vectors_by_id.get(document_id, [])]),
                anchor_vectors,
            ),
        )
        for document_id, chunks in chunks_by_id.items()
    }


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
        items = build_links(
            source_document=source_embedded,
            candidate_documents=candidate_embedded,
            semantic_scores_by_id=semantic_scores_by_id,
            settings=settings,
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
        items.extend(
            build_links(
                source_document=source_embedded,
                candidate_documents=candidate_embedded,
                semantic_scores_by_id={},
                settings=settings,
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
