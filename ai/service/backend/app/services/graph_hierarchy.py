"""Embedding-based hierarchy linker for the graph view.

The production pattern follows parent-child chunking used by RAG systems:
small semantic chunks are embedded, then the graph asks whether one document's
chunk set semantically covers another document's chunk set.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GraphDocument:
    document_id: str
    title: str = ""
    category: str = ""
    tags: tuple[str, ...] = ()
    summary: str = ""
    raw_text: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class GraphLinkSettings:
    max_top_k: int = 8
    max_edges_per_doc: int = 3
    min_parent_score: float = 0.33
    min_similar_score: float = 0.55
    parent_margin: float = 0.02
    min_generality_delta: float = 0.015
    min_parent_generality: float = 0.46
    min_parent_topic_alignment: float = 0.59
    max_chunks_per_doc: int = 12
    chunk_target_chars: int = 420
    chunk_overlap_sentences: int = 1


@dataclass(frozen=True)
class EmbeddedGraphDocument:
    document: GraphDocument
    chunks: tuple[str, ...]
    vectors: tuple[tuple[float, ...], ...]
    generality: float = 0.5


GENERALITY_ANCHORS: tuple[str, ...] = (
    "상위 개념, 기본 원리, 전체 구조, 여러 하위 주제를 포괄적으로 설명하는 개요 문서",
    "theoretical overview that explains broad concepts, principles, taxonomy, and relationships",
)

SPECIFICITY_ANCHORS: tuple[str, ...] = (
    "구체적인 수행 항목, 제출물, 시험 문항, 일정 안내, 결제 내역처럼 특정 사건이나 작업에 대한 문서",
    "specific task, assignment, exam question, announcement, receipt, transaction, or personal note",
)


def _compact_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def build_graph_text(document: GraphDocument) -> str:
    tags = ", ".join(document.tags)
    parts = [
        f"Title: {_compact_text(document.title)}",
        f"Tags: {tags}",
        f"Summary: {_compact_text(document.summary)}",
        f"Body: {_compact_text(document.raw_text)[:1600]}",
    ]
    return "\n".join(part for part in parts if part.split(":", 1)[1].strip())


def _split_sentences(text: str) -> list[str]:
    normalized = _compact_text(text)
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", normalized)
    return [item.strip() for item in sentences if item.strip()]


def split_graph_chunks(document: GraphDocument, settings: GraphLinkSettings) -> list[str]:
    """Create semantic chunks without stopword-based parsing."""

    chunks: list[str] = []
    header_parts = [
        f"Title: {_compact_text(document.title)}",
        f"Tags: {', '.join(document.tags)}",
        f"Summary: {_compact_text(document.summary)}",
    ]
    header = "\n".join(part for part in header_parts if part.split(":", 1)[1].strip())
    if header:
        chunks.append(header)

    sentences = _split_sentences(document.raw_text)
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        sentence_len = len(sentence)
        if current and current_len + sentence_len > settings.chunk_target_chars:
            chunks.append(" ".join(current))
            overlap = max(0, settings.chunk_overlap_sentences)
            current = current[-overlap:] if overlap else []
            current_len = sum(len(item) for item in current)
        current.append(sentence)
        current_len += sentence_len

    if current:
        chunks.append(" ".join(current))

    if not chunks:
        fallback = build_graph_text(document)
        if fallback:
            chunks.append(fallback)

    return chunks[: max(1, settings.max_chunks_per_doc)]


def _vector_norm(vector: tuple[float, ...]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _cosine_similarity(source: tuple[float, ...], target: tuple[float, ...]) -> float:
    if not source or not target or len(source) != len(target):
        return 0.0
    source_norm = _vector_norm(source)
    target_norm = _vector_norm(target)
    if source_norm == 0.0 or target_norm == 0.0:
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(source, target)) / (source_norm * target_norm)))


def _mean_vector(vectors: tuple[tuple[float, ...], ...]) -> tuple[float, ...]:
    if not vectors:
        return ()
    vector_size = len(vectors[0])
    if vector_size == 0:
        return ()
    return tuple(sum(vector[index] for vector in vectors) / len(vectors) for index in range(vector_size))


def graph_role_anchor_texts() -> list[str]:
    return [*GENERALITY_ANCHORS, *SPECIFICITY_ANCHORS]


def estimate_generality(
    document_vectors: tuple[tuple[float, ...], ...],
    anchor_vectors: tuple[tuple[float, ...], ...],
) -> float:
    document_vector = _mean_vector(document_vectors)
    if not document_vector or len(anchor_vectors) < len(GENERALITY_ANCHORS) + len(SPECIFICITY_ANCHORS):
        return 0.5

    general_anchor = _mean_vector(anchor_vectors[: len(GENERALITY_ANCHORS)])
    specific_anchor = _mean_vector(anchor_vectors[len(GENERALITY_ANCHORS) :])
    general_score = _cosine_similarity(document_vector, general_anchor)
    specific_score = _cosine_similarity(document_vector, specific_anchor)
    # Keep the value bounded and centered around 0.5 so it is a weak semantic
    # role prior, not a replacement for chunk coverage.
    return round(max(0.0, min(1.0, 0.5 + ((general_score - specific_score) * 0.5))), 4)


def _document_scope_size(document: GraphDocument, chunks: tuple[str, ...]) -> int:
    text_size = len(_compact_text(document.title))
    text_size += len(" ".join(document.tags))
    text_size += len(_compact_text(document.summary))
    text_size += len(_compact_text(document.raw_text))
    # Chunk count matters, but only as a weak scope signal from document content.
    return max(1, text_size + (len(chunks) * 120))


def _scope_delta(parent: EmbeddedGraphDocument, child: EmbeddedGraphDocument) -> float:
    parent_scope = _document_scope_size(parent.document, parent.chunks)
    child_scope = _document_scope_size(child.document, child.chunks)
    if child_scope >= parent_scope:
        return 0.0
    return round(min(1.0, (parent_scope - child_scope) / max(parent_scope, 1)), 4)


def _chunk_coverage(
    parent: EmbeddedGraphDocument,
    child: EmbeddedGraphDocument,
) -> tuple[float, float, list[dict[str, Any]]]:
    if not parent.vectors or not child.vectors:
        return 0.0, 0.0, []

    best_matches: list[tuple[float, int, int]] = []
    for child_index, child_vector in enumerate(child.vectors):
        best_score = 0.0
        best_parent_index = 0
        for parent_index, parent_vector in enumerate(parent.vectors):
            score = _cosine_similarity(parent_vector, child_vector)
            if score > best_score:
                best_score = score
                best_parent_index = parent_index
        best_matches.append((best_score, best_parent_index, child_index))

    if not best_matches:
        return 0.0, 0.0, []

    avg_best = sum(score for score, _parent_index, _child_index in best_matches) / len(best_matches)
    strong_match_ratio = sum(1 for score, _parent_index, _child_index in best_matches if score >= 0.68) / len(best_matches)
    coverage = round((avg_best * 0.7) + (strong_match_ratio * 0.3), 4)
    matched_parent_indices = {parent_index for score, parent_index, _child_index in best_matches if score >= 0.68}
    breadth = round(min(1.0, len(matched_parent_indices) / max(1, len(parent.vectors))), 4)

    reasons = [
        {
            "score": round(score, 4),
            "parent_chunk": parent.chunks[parent_index][:180],
            "child_chunk": child.chunks[child_index][:180],
        }
        for score, parent_index, child_index in sorted(best_matches, reverse=True)[:3]
    ]
    return coverage, breadth, reasons


def _topic_alignment(source: EmbeddedGraphDocument, target: EmbeddedGraphDocument, semantic_similarity: float | None) -> float:
    source_doc_vector = _mean_vector(source.vectors)
    target_doc_vector = _mean_vector(target.vectors)
    # Qdrant query scores are directional because the query text changes per
    # source document. Use them for ranking candidates only, never for pairwise
    # hierarchy scoring, or reciprocal parent edges can appear.
    return round(_cosine_similarity(source_doc_vector, target_doc_vector), 4)


def _parent_score(
    parent: EmbeddedGraphDocument,
    child: EmbeddedGraphDocument,
    topic_alignment: float,
) -> tuple[float, dict[str, Any]]:
    coverage, breadth, matches = _chunk_coverage(parent, child)
    scope_delta = _scope_delta(parent, child)
    generality_delta = round(max(0.0, parent.generality - child.generality), 4)
    score = round(
        (0.48 * coverage)
        + (0.12 * scope_delta)
        + (0.10 * topic_alignment)
        + (0.06 * breadth)
        + (0.24 * generality_delta),
        4,
    )
    return score, {
        "coverage": coverage,
        "breadth": breadth,
        "scope_delta": scope_delta,
        "generality": parent.generality,
        "child_generality": child.generality,
        "generality_delta": generality_delta,
        "topic_alignment": topic_alignment,
        "matched_chunks": matches,
    }


def score_relationship(
    source: EmbeddedGraphDocument,
    target: EmbeddedGraphDocument,
    semantic_similarity: float | None,
    settings: GraphLinkSettings,
) -> dict[str, Any]:
    topic_alignment = _topic_alignment(source, target, semantic_similarity)
    source_parent_score, source_reason = _parent_score(source, target, topic_alignment)
    target_parent_score, target_reason = _parent_score(target, source, topic_alignment)
    margin = abs(source_parent_score - target_parent_score)

    source_generality_delta = float(source_reason.get("generality_delta") or 0.0)
    target_generality_delta = float(target_reason.get("generality_delta") or 0.0)
    generality_parent_floor = max(0.22, settings.min_parent_score * 0.65)

    source_generality_backed = (
        source_parent_score >= generality_parent_floor
        and topic_alignment >= settings.min_parent_topic_alignment
        and source.generality >= settings.min_parent_generality
        and source_generality_delta >= settings.min_generality_delta
        and source_generality_delta > target_generality_delta
    )
    target_generality_backed = (
        target_parent_score >= generality_parent_floor
        and topic_alignment >= settings.min_parent_topic_alignment
        and target.generality >= settings.min_parent_generality
        and target_generality_delta >= settings.min_generality_delta
        and target_generality_delta > source_generality_delta
    )

    if (
        source_generality_backed
        or (
            source_parent_score >= settings.min_parent_score
            and margin >= settings.parent_margin
            and topic_alignment >= settings.min_parent_topic_alignment
            and source.generality >= settings.min_parent_generality
            and source_generality_delta >= settings.min_generality_delta
        )
    ):
        return {
            "source": source.document.document_id,
            "target": target.document.document_id,
            "edge_type": "parent_of",
            "score": source_parent_score,
            "reason": {
                "basis": "chunk_embedding_coverage",
                "parent_score": source_parent_score,
                "reverse_parent_score": target_parent_score,
                "margin": round(margin, 4),
                **source_reason,
                "summary": "source document chunks semantically cover the target document chunks",
            },
        }

    if (
        target_generality_backed
        or (
            target_parent_score >= settings.min_parent_score
            and margin >= settings.parent_margin
            and topic_alignment >= settings.min_parent_topic_alignment
            and target.generality >= settings.min_parent_generality
            and target_generality_delta >= settings.min_generality_delta
        )
    ):
        return {
            "source": target.document.document_id,
            "target": source.document.document_id,
            "edge_type": "parent_of",
            "score": target_parent_score,
            "reason": {
                "basis": "chunk_embedding_coverage",
                "parent_score": target_parent_score,
                "reverse_parent_score": source_parent_score,
                "margin": round(margin, 4),
                **target_reason,
                "summary": "target document chunks semantically cover the source document chunks",
            },
        }

    source_id, target_id = sorted((source.document.document_id, target.document.document_id))
    similar_score = round(topic_alignment, 4)
    return {
        "source": source_id,
        "target": target_id,
        "edge_type": "similar_to",
        "score": similar_score,
            "reason": {
                "basis": "chunk_embedding_alignment",
                "parent_score_a_to_b": source_parent_score,
                "parent_score_b_to_a": target_parent_score,
                "margin": round(margin, 4),
                "source_generality": source_reason.get("generality"),
                "target_generality": target_reason.get("generality"),
                "source_generality_delta": source_generality_delta,
                "target_generality_delta": target_generality_delta,
                "topic_alignment": topic_alignment,
                "summary": "documents are semantically close, but parent-child direction is uncertain",
            },
    }


def _rank_candidates(
    source: EmbeddedGraphDocument,
    candidates: list[EmbeddedGraphDocument],
    semantic_scores_by_id: dict[str, float],
    limit: int,
) -> list[tuple[EmbeddedGraphDocument, float | None]]:
    ranked: list[tuple[float, EmbeddedGraphDocument, float | None]] = []
    for candidate in candidates:
        if candidate.document.document_id == source.document.document_id:
            continue
        semantic_score = semantic_scores_by_id.get(candidate.document.document_id)
        alignment = _topic_alignment(source, candidate, semantic_score)
        ranked.append((alignment, candidate, semantic_score))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [(candidate, semantic_score) for _alignment, candidate, semantic_score in ranked[:limit]]


def build_links(
    *,
    source_document: EmbeddedGraphDocument,
    candidate_documents: list[EmbeddedGraphDocument],
    semantic_scores_by_id: dict[str, float],
    settings: GraphLinkSettings,
) -> list[dict[str, Any]]:
    if not source_document.vectors:
        return []

    ranked_candidates = _rank_candidates(
        source_document,
        [candidate for candidate in candidate_documents if candidate.vectors],
        semantic_scores_by_id,
        limit=settings.max_top_k,
    )
    scored = [
        score_relationship(source_document, candidate, semantic_score, settings)
        for candidate, semantic_score in ranked_candidates
    ]
    parent_floor = max(0.22, settings.min_parent_score * 0.65)
    selected = [
        item
        for item in scored
        if (
            item["edge_type"] == "parent_of"
            and float(item["score"]) >= parent_floor
        )
        or (
            item["edge_type"] == "similar_to"
            and float(item["score"]) >= settings.min_similar_score
        )
    ]
    selected.sort(key=lambda item: float(item["score"]), reverse=True)
    return selected[: settings.max_edges_per_doc]
