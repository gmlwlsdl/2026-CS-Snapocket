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
    max_edges: int | None = Field(default=None, ge=1, le=10)
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
    )


def _embed_documents(
    documents: list[GraphDocument],
    settings: GraphLinkSettings,
    service,
) -> dict[str, EmbeddedGraphDocument]:
    chunks_by_id = {
        document.document_id: split_graph_chunks(document, settings)
        for document in documents
    }
    flat_chunks: list[str] = []
    flat_refs: list[tuple[str, int]] = []
    for document_id, chunks in chunks_by_id.items():
        for index, chunk in enumerate(chunks):
            flat_refs.append((document_id, index))
            flat_chunks.append(chunk)

    anchor_texts = graph_role_anchor_texts()
    vectors = service.encode_texts([*flat_chunks, *anchor_texts])
    chunk_vectors = vectors[: len(flat_chunks)]
    anchor_vectors = tuple(tuple(float(value) for value in vector) for vector in vectors[len(flat_chunks) :])
    vectors_by_id: dict[str, list[tuple[float, ...]]] = {document.document_id: [] for document in documents}
    for (document_id, _index), vector in zip(flat_refs, chunk_vectors):
        vectors_by_id[document_id].append(tuple(float(value) for value in vector))

    documents_by_id = {document.document_id: document for document in documents}
    return {
        document_id: EmbeddedGraphDocument(
            document=documents_by_id[document_id],
            chunks=tuple(chunks),
            vectors=tuple(vectors_by_id.get(document_id, [])),
            generality=estimate_generality(tuple(vectors_by_id.get(document_id, [])), anchor_vectors),
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
    candidate_documents = [_to_graph_document(item) for item in payload.candidate_documents]
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
                "candidates_considered": len(candidate_documents),
                "skipped_reason": "semantic embedding service is unavailable",
            },
        )

    try:
        embedded_by_id = _embed_documents([source_document, *candidate_documents], settings, service)
        semantic_available = True
    except SemanticSearchUnavailable as exc:
        return ok_response(
            request,
            {
                "items": [],
                "semantic_available": False,
                "candidates_considered": len(candidate_documents),
                "skipped_reason": str(exc),
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
            "candidates_considered": len(candidate_documents),
        },
    )
