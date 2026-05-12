import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from core.config import GRAPH_MAX_EDGES_PER_DOC, GRAPH_MAX_TOP_K, GRAPH_RUN_WHEN_VLM_IDLE
from models.analysis_job import AnalysisJob
from models.document import Document
from models.graph_edge import GraphEdge
from services.semantic_search import SemanticSearchError, request_graph_links, request_graph_links_batch

PARENT_CANDIDATE_TYPES = {"parent_candidate", "parent_of"}
RELATED_CANDIDATE_TYPES = {"related_candidate", "related_to", "similar_to"}
ROOT_CANDIDATE_TYPES = {"new_root_candidate"}
FINAL_EDGE_TYPES = {"parent_of", "related_to", "similar_to"}
REJECTED_PARENT_RELATED_MIN_SCORE = 0.58
REJECTED_PARENT_MAX_NEGATIVE_EVIDENCE = 0.30
PARENT_MIN_SCORE = 0.29
PARENT_MIN_COVERAGE = 0.32
PARENT_MIN_SOURCE_GENERALITY = 0.49
PARENT_MIN_GENERALITY_DELTA = 0.015
PARENT_MIN_TOPIC_ALIGNMENT = 0.58
PARENT_MIN_ENTAILMENT_LIKE_SCORE = 0.32
PARENT_MIN_DIRECTNESS = 0.025
PARENT_MAX_NEGATIVE_EVIDENCE = 0.24
PARENT_AMBIGUOUS_DIRECTNESS = 0.035
PARENT_AMBIGUOUS_TOPIC_ALIGNMENT = 0.62
PARENT_AMBIGUOUS_COVERAGE = 0.38

def _serialize_datetime(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _serialize_graph_document(document: Document) -> dict:
    # Graph links are semantic relationships between document contents.
    # Display metadata such as title, category, tags, and summary must not
    # influence embedding similarity or hierarchy decisions.
    return {
        "document_id": str(document.id),
        "raw_text": str(document.raw_text or ""),
        "updated_at": _serialize_datetime(document.updated_at),
    }


def _candidate_documents(
    *,
    db: Session,
    user_id: str,
    source_document_id: str,
    limit: int,
) -> list[Document]:
    return (
        db.query(Document)
        .options(joinedload(Document.tag_objects))
        .filter(
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
            Document.id != source_document_id,
        )
        .order_by(Document.updated_at.desc(), Document.created_at.desc())
        .limit(max(limit, GRAPH_MAX_TOP_K))
        .all()
    )


def _has_active_analysis_jobs(db: Session) -> bool:
    return (
        db.query(AnalysisJob.id)
        .filter(AnalysisJob.status == "processing")
        .limit(1)
        .first()
        is not None
    )


def _delete_incident_edges(*, db: Session, user_id: str, document_id: str) -> int:
    deleted = db.query(GraphEdge).filter(
        GraphEdge.user_id == user_id,
        or_(
            GraphEdge.source_document_id == document_id,
            GraphEdge.target_document_id == document_id,
        ),
    ).delete(synchronize_session=False)
    return int(deleted or 0)


def delete_user_graph_edges(*, db: Session, user_id: str) -> int:
    deleted = db.query(GraphEdge).filter(GraphEdge.user_id == user_id).delete(synchronize_session=False)
    db.commit()
    return int(deleted or 0)


def _graph_edge_key(edge: GraphEdge) -> tuple[str, str, str]:
    return (
        str(edge.source_document_id),
        str(edge.target_document_id),
        str(edge.edge_type),
    )


def _parent_slot_key(edge_type: str, target_id: str) -> str | None:
    return target_id if edge_type == "parent_of" else None


def _document_ids_for_user(*, db: Session, user_id: str) -> set[str]:
    return {
        str(document_id)
        for (document_id,) in (
            db.query(Document.id)
            .filter(
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
            )
            .all()
        )
    }


def _normalize_candidate_item(item: dict[str, Any], document_ids: set[str]) -> dict[str, Any] | None:
    source_id = str(item.get("source") or "")
    target_id = str(item.get("target") or "")
    edge_type = str(item.get("edge_type") or "related_candidate")
    score = float(item.get("score") or 0.0)
    reason = item.get("reason") if isinstance(item.get("reason"), dict) else {}

    if edge_type in ROOT_CANDIDATE_TYPES:
        return {
            "source": source_id,
            "target": "",
            "edge_type": "new_root_candidate",
            "score": score,
            "reason": reason,
        }

    if not source_id or not target_id or source_id == target_id:
        return None
    if document_ids and (source_id not in document_ids or target_id not in document_ids):
        return None

    if edge_type in PARENT_CANDIDATE_TYPES:
        return {
            "source": source_id,
            "target": target_id,
            "edge_type": "parent_candidate",
            "score": score,
            "reason": reason,
        }
    if edge_type in RELATED_CANDIDATE_TYPES:
        final_type = "similar_to" if edge_type == "similar_to" else "related_to"
        ordered_source, ordered_target = sorted((source_id, target_id))
        return {
            "source": ordered_source,
            "target": ordered_target,
            "edge_type": final_type,
            "score": score,
            "reason": reason,
        }
    return None


def _would_create_cycle_in_memory(
    *,
    children_by_parent: dict[str, set[str]],
    source_id: str,
    target_id: str,
) -> bool:
    stack = [target_id]
    visited: set[str] = set()
    while stack:
        current = stack.pop()
        if current == source_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(children_by_parent.get(current, set()))
    return False


def _to_related_from_rejected_parent(
    candidate: dict[str, Any],
    *,
    selected_parent_id: str | None = None,
    rejection: str,
) -> dict[str, Any] | None:
    source_id = str(candidate.get("source") or "")
    target_id = str(candidate.get("target") or "")
    if not source_id or not target_id or source_id == target_id:
        return None

    reason = candidate.get("reason") if isinstance(candidate.get("reason"), dict) else {}
    score = float(candidate.get("score") or 0.0)
    negative_evidence = float(reason.get("negative_evidence") or 0.0)
    topic_alignment = float(reason.get("topic_alignment") or 0.0)
    related_score = max(score, topic_alignment)
    if related_score < REJECTED_PARENT_RELATED_MIN_SCORE:
        return None
    if negative_evidence > REJECTED_PARENT_MAX_NEGATIVE_EVIDENCE:
        return None

    source_id, target_id = sorted((source_id, target_id))
    return {
        "source": source_id,
        "target": target_id,
        "edge_type": "related_to",
        "score": related_score,
        "reason": {
            **reason,
            "basis": reason.get("basis") or "rejected_parent_candidate",
            "rejection": rejection,
            "selected_parent_id": selected_parent_id,
            "summary": "parent candidate was preserved as a non-structural relation",
        },
    }


def _passes_conservative_parent_constraints(candidate: dict[str, Any]) -> tuple[bool, str]:
    reason = candidate.get("reason") if isinstance(candidate.get("reason"), dict) else {}
    score = float(candidate.get("score") or 0.0)
    directness = float(reason.get("directness") or 0.0)
    topic_alignment = float(reason.get("topic_alignment") or 0.0)
    coverage_evidence = max(
        float(reason.get("coverage") or 0.0),
        float(reason.get("bridge_alignment") or 0.0) * 0.82,
    )
    generality_delta = float(reason.get("generality_delta") or 0.0)
    ambiguous = bool(reason.get("ambiguity"))
    ambiguity_supported = (
        not ambiguous
        or directness >= PARENT_AMBIGUOUS_DIRECTNESS
        or (
            topic_alignment >= PARENT_AMBIGUOUS_TOPIC_ALIGNMENT
            and coverage_evidence >= PARENT_AMBIGUOUS_COVERAGE
            and generality_delta >= PARENT_MIN_GENERALITY_DELTA
        )
    )
    checks = {
        "score": score >= PARENT_MIN_SCORE,
        "coverage": coverage_evidence >= PARENT_MIN_COVERAGE,
        "source_generality": float(reason.get("generality") or 0.0) >= PARENT_MIN_SOURCE_GENERALITY,
        "generality_delta": generality_delta >= PARENT_MIN_GENERALITY_DELTA,
        "topic_alignment": topic_alignment >= PARENT_MIN_TOPIC_ALIGNMENT,
        "entailment_like_score": float(reason.get("entailment_like_score") or 0.0)
        >= PARENT_MIN_ENTAILMENT_LIKE_SCORE,
        "directness": directness >= PARENT_MIN_DIRECTNESS,
        "negative_evidence": float(reason.get("negative_evidence") or 0.0) <= PARENT_MAX_NEGATIVE_EVIDENCE,
        "ambiguity_supported": ambiguity_supported,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        return False, "parent_constraints:" + ",".join(failed)
    return True, ""


def _resolve_graph_candidate_edges(
    items: list[dict[str, Any]],
    *,
    document_ids: set[str],
) -> list[dict[str, Any]]:
    """Resolve AI candidates into a single-parent forest plus auxiliary links."""

    normalized = [
        candidate
        for item in items
        if isinstance(item, dict)
        for candidate in [_normalize_candidate_item(item, document_ids)]
        if candidate is not None
    ]
    parent_candidates = [
        candidate
        for candidate in normalized
        if candidate["edge_type"] == "parent_candidate"
    ]
    auxiliary_candidates = [
        candidate
        for candidate in normalized
        if candidate["edge_type"] in {"related_to", "similar_to"}
    ]

    parent_candidates.sort(
        key=lambda candidate: (
            float(candidate.get("score") or 0.0),
            float((candidate.get("reason") or {}).get("directness") or 0.0),
            float((candidate.get("reason") or {}).get("margin") or 0.0),
        ),
        reverse=True,
    )

    selected_parent_by_child: dict[str, dict[str, Any]] = {}
    children_by_parent: dict[str, set[str]] = {}
    selected_edges: list[dict[str, Any]] = []
    rejected_as_related: list[dict[str, Any]] = []

    for candidate in parent_candidates:
        source_id = str(candidate["source"])
        target_id = str(candidate["target"])
        reason = candidate.get("reason") if isinstance(candidate.get("reason"), dict) else {}
        directness = float(reason.get("directness") or 0.0)
        margin = float(reason.get("margin") or 0.0)
        ambiguous = bool(reason.get("ambiguity")) and max(directness, margin) < 0.045

        passed, rejection = _passes_conservative_parent_constraints(candidate)
        if not passed:
            related = _to_related_from_rejected_parent(candidate, rejection=rejection)
            if related:
                rejected_as_related.append(related)
            continue

        if ambiguous:
            related = _to_related_from_rejected_parent(candidate, rejection="ambiguous_parent_margin")
            if related:
                rejected_as_related.append(related)
            continue

        existing_parent = selected_parent_by_child.get(target_id)
        if existing_parent is not None:
            if str(existing_parent["source"]) == source_id:
                continue
            related = _to_related_from_rejected_parent(
                candidate,
                selected_parent_id=str(existing_parent["source"]),
                rejection="single_parent_constraint",
            )
            if related:
                rejected_as_related.append(related)
            continue

        if _would_create_cycle_in_memory(
            children_by_parent=children_by_parent,
            source_id=source_id,
            target_id=target_id,
        ):
            related = _to_related_from_rejected_parent(candidate, rejection="cycle_prevention")
            if related:
                rejected_as_related.append(related)
            continue

        final_edge = {
            **candidate,
            "edge_type": "parent_of",
        }
        selected_parent_by_child[target_id] = final_edge
        children_by_parent.setdefault(source_id, set()).add(target_id)
        selected_edges.append(final_edge)

    parent_pair_keys = {
        tuple(sorted((str(edge["source"]), str(edge["target"]))))
        for edge in selected_edges
    }
    deduped_auxiliary: dict[tuple[str, str, str], dict[str, Any]] = {}
    for candidate in [*auxiliary_candidates, *rejected_as_related]:
        source_id = str(candidate.get("source") or "")
        target_id = str(candidate.get("target") or "")
        edge_type = str(candidate.get("edge_type") or "related_to")
        if edge_type not in {"related_to", "similar_to"} or not source_id or not target_id or source_id == target_id:
            continue
        if tuple(sorted((source_id, target_id))) in parent_pair_keys:
            continue
        key = (source_id, target_id, edge_type)
        existing = deduped_auxiliary.get(key)
        if existing is None or float(candidate.get("score") or 0.0) > float(existing.get("score") or 0.0):
            deduped_auxiliary[key] = candidate

    return [*selected_edges, *deduped_auxiliary.values()]


def _would_create_parent_cycle(
    *,
    db: Session,
    user_id: str,
    source_id: str,
    target_id: str,
) -> bool:
    stack = [target_id]
    visited: set[str] = set()
    while stack:
        current = stack.pop()
        if current == source_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        child_ids = [
            str(child_id)
            for (child_id,) in (
                db.query(GraphEdge.target_document_id)
                .filter(
                    GraphEdge.user_id == user_id,
                    GraphEdge.source_document_id == current,
                    GraphEdge.edge_type == "parent_of",
                    GraphEdge.status == "active",
                )
                .all()
            )
        ]
        stack.extend(child_ids)
    return False


def _prune_duplicate_parent_edges(*, db: Session, user_id: str) -> int:
    duplicate_targets = [
        str(target_id)
        for (target_id,) in (
            db.query(GraphEdge.target_document_id)
            .filter(
                GraphEdge.user_id == user_id,
                GraphEdge.edge_type == "parent_of",
                GraphEdge.status == "active",
            )
            .group_by(GraphEdge.target_document_id)
            .having(func.count(GraphEdge.id) > 1)
            .all()
        )
    ]

    deleted = 0
    for target_id in duplicate_targets:
        parent_edges = (
            db.query(GraphEdge)
            .filter(
                GraphEdge.user_id == user_id,
                GraphEdge.target_document_id == target_id,
                GraphEdge.edge_type == "parent_of",
                GraphEdge.status == "active",
            )
            .order_by(GraphEdge.score.desc(), GraphEdge.updated_at.desc(), GraphEdge.created_at.desc())
            .all()
        )
        for edge in parent_edges[1:]:
            db.delete(edge)
            deleted += 1
    return deleted


def _upsert_edge(
    *,
    db: Session,
    user_id: str,
    source_id: str,
    target_id: str,
    edge_type: str,
    score: float,
    reason: dict,
) -> dict[str, object]:
    if not source_id or not target_id or source_id == target_id:
        return {"status": "skipped", "deleted": 0, "edge_key": None}
    if edge_type not in FINAL_EDGE_TYPES:
        return {"status": "skipped", "deleted": 0, "edge_key": None}

    deleted = 0
    db.flush()
    if edge_type == "parent_of":
        if _would_create_parent_cycle(db=db, user_id=user_id, source_id=source_id, target_id=target_id):
            return {"status": "skipped", "deleted": 0, "edge_key": None}

        reverse = (
            db.query(GraphEdge)
            .filter(
                GraphEdge.user_id == user_id,
                GraphEdge.source_document_id == target_id,
                GraphEdge.target_document_id == source_id,
                GraphEdge.edge_type == "parent_of",
            )
            .first()
        )
        if reverse is not None:
            if float(reverse.score or 0.0) >= score:
                return {
                    "status": "skipped",
                    "deleted": 0,
                    "edge_key": _graph_edge_key(reverse),
                }
            db.delete(reverse)
            deleted += 1

        existing_parents = (
            db.query(GraphEdge)
            .filter(
                GraphEdge.user_id == user_id,
                GraphEdge.target_document_id == target_id,
                GraphEdge.edge_type == "parent_of",
                GraphEdge.source_document_id != source_id,
            )
            .all()
        )
        stronger_parent = max(
            existing_parents,
            key=lambda edge: float(edge.score or 0.0),
            default=None,
        )
        if stronger_parent is not None and float(stronger_parent.score or 0.0) >= score:
            return {
                "status": "skipped",
                "deleted": deleted,
                "edge_key": _graph_edge_key(stronger_parent),
            }
        for parent_edge in existing_parents:
            db.delete(parent_edge)
            deleted += 1
        if deleted:
            db.flush()

    existing = (
        db.query(GraphEdge)
        .filter(
            GraphEdge.user_id == user_id,
            GraphEdge.source_document_id == source_id,
            GraphEdge.target_document_id == target_id,
            GraphEdge.edge_type == edge_type,
        )
        .first()
    )
    reason_json = json.dumps(reason, ensure_ascii=False)
    if existing is not None:
        existing.score = score
        existing.reason_json = reason_json
        existing.status = "active"
        existing.parent_slot_key = _parent_slot_key(edge_type, target_id)
        return {
            "status": "updated",
            "deleted": deleted,
            "edge_key": (source_id, target_id, edge_type),
        }

    db.add(
        GraphEdge(
            id=str(uuid.uuid4()),
            user_id=str(user_id),
            source_document_id=source_id,
            target_document_id=target_id,
            edge_type=edge_type,
            parent_slot_key=_parent_slot_key(edge_type, target_id),
            score=score,
            reason_json=reason_json,
            status="active",
        )
    )
    return {
        "status": "created",
        "deleted": deleted,
        "edge_key": (source_id, target_id, edge_type),
    }


def refresh_document_edges(
    *,
    db: Session,
    document_id: str,
    user_id: str,
    limit: int | None = None,
    max_edges: int | None = None,
    min_score: float | None = None,
    delete_existing: bool = True,
) -> dict[str, object]:
    if GRAPH_RUN_WHEN_VLM_IDLE and _has_active_analysis_jobs(db):
        return {"deleted": 0, "created": 0, "updated": 0, "skipped": 1}

    source_document = (
        db.query(Document)
        .options(joinedload(Document.tag_objects))
        .filter(
            Document.id == document_id,
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if source_document is None:
        deleted = _delete_incident_edges(db=db, user_id=user_id, document_id=document_id)
        db.commit()
        return {"deleted": deleted, "created": 0, "updated": 0}

    candidate_documents = _candidate_documents(
        db=db,
        user_id=user_id,
        source_document_id=str(source_document.id),
        limit=limit or GRAPH_MAX_TOP_K,
    )
    link_limit = min(50, limit or GRAPH_MAX_TOP_K)
    link_max_edges = min(10, max_edges or GRAPH_MAX_EDGES_PER_DOC)
    payload = {
        "user_id": str(user_id),
        "source_document": _serialize_graph_document(source_document),
        "candidate_documents": [_serialize_graph_document(document) for document in candidate_documents],
        "limit": link_limit,
        "max_edges": link_max_edges,
    }
    if min_score is not None:
        payload["min_parent_score"] = min_score
        payload["min_similar_score"] = min_score

    try:
        link_result = request_graph_links(payload)
    except SemanticSearchError:
        return {"deleted": 0, "created": 0, "updated": 0, "skipped": 1}
    if link_result.get("skipped_reason"):
        return {"deleted": 0, "created": 0, "updated": 0, "skipped": 1}

    deleted = 0
    if delete_existing:
        deleted = _delete_incident_edges(db=db, user_id=user_id, document_id=document_id)

    created = 0
    updated = 0
    edge_keys: list[tuple[str, str, str]] = []
    resolved_edges = _resolve_graph_candidate_edges(
        link_result.get("items") if isinstance(link_result.get("items"), list) else [],
        document_ids=_document_ids_for_user(db=db, user_id=str(user_id)),
    )
    for item in resolved_edges:
        source_id = str(item.get("source") or "")
        target_id = str(item.get("target") or "")
        edge_type = str(item.get("edge_type") or "related_to")
        upsert_result = _upsert_edge(
            db=db,
            user_id=str(user_id),
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            score=float(item.get("score") or 0.0),
            reason=item.get("reason") if isinstance(item.get("reason"), dict) else {},
        )
        deleted += int(upsert_result.get("deleted", 0) or 0)
        edge_key = upsert_result.get("edge_key")
        if isinstance(edge_key, tuple) and len(edge_key) == 3:
            edge_keys.append(edge_key)

        status = str(upsert_result.get("status") or "skipped")
        if status == "created":
            created += 1
        elif status == "updated":
            updated += 1

    deleted += _prune_duplicate_parent_edges(db=db, user_id=str(user_id))
    db.commit()
    return {"deleted": deleted, "created": created, "updated": updated, "skipped": 0, "edge_keys": edge_keys}


def _graph_documents_for_user(*, db: Session, user_id: str) -> list[Document]:
    return (
        db.query(Document)
        .options(joinedload(Document.tag_objects))
        .filter(
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.updated_at.desc(), Document.created_at.desc())
        .all()
    )


def rebuild_user_graph_edges(*, db: Session, user_id: str) -> dict[str, object]:
    if GRAPH_RUN_WHEN_VLM_IDLE and _has_active_analysis_jobs(db):
        return {"document_count": 0, "deleted": 0, "created": 0, "updated": 0, "skipped": 1}

    documents = _graph_documents_for_user(db=db, user_id=user_id)
    document_ids = {str(document.id) for document in documents}
    payload = {
        "user_id": str(user_id),
        "documents": [_serialize_graph_document(document) for document in documents],
        "limit": min(50, max(GRAPH_MAX_TOP_K, max(1, len(documents) - 1))),
        "max_edges": min(14, max(GRAPH_MAX_EDGES_PER_DOC, 14)),
    }
    try:
        link_result = request_graph_links_batch(payload)
    except SemanticSearchError:
        return {
            "document_count": len(documents),
            "deleted": 0,
            "created": 0,
            "updated": 0,
            "skipped": 1,
        }
    if link_result.get("skipped_reason"):
        return {
            "document_count": len(documents),
            "deleted": 0,
            "created": 0,
            "updated": 0,
            "skipped": 1,
        }
    candidate_items = [
        item
        for item in link_result.get("items", [])
        if isinstance(item, dict)
    ]

    resolved_edges = _resolve_graph_candidate_edges(candidate_items, document_ids=document_ids)

    deleted = int(
        db.query(GraphEdge)
        .filter(GraphEdge.user_id == user_id)
        .delete(synchronize_session=False)
        or 0
    )
    db.flush()

    created = 0
    updated = 0
    for edge in resolved_edges:
        upsert_result = _upsert_edge(
            db=db,
            user_id=user_id,
            source_id=str(edge.get("source") or ""),
            target_id=str(edge.get("target") or ""),
            edge_type=str(edge.get("edge_type") or "related_to"),
            score=float(edge.get("score") or 0.0),
            reason=edge.get("reason") if isinstance(edge.get("reason"), dict) else {},
        )
        status = str(upsert_result.get("status") or "skipped")
        if status == "created":
            created += 1
        elif status == "updated":
            updated += 1
        deleted += int(upsert_result.get("deleted", 0) or 0)

    deleted += _prune_duplicate_parent_edges(db=db, user_id=user_id)
    db.commit()
    return {
        "document_count": len(documents),
        "deleted": deleted,
        "created": created,
        "updated": updated,
        "skipped": 0,
        "parent_edges": sum(1 for edge in resolved_edges if edge.get("edge_type") == "parent_of"),
        "auxiliary_edges": sum(1 for edge in resolved_edges if edge.get("edge_type") in {"related_to", "similar_to"}),
    }


def delete_document_edges(*, db: Session, user_id: str, document_id: str) -> int:
    deleted = _delete_incident_edges(db=db, user_id=user_id, document_id=document_id)
    db.commit()
    return deleted
