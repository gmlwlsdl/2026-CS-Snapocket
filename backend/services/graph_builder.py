import json
import uuid
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from core.config import GRAPH_MAX_EDGES_PER_DOC, GRAPH_MAX_TOP_K, GRAPH_RUN_WHEN_VLM_IDLE
from models.analysis_job import AnalysisJob
from models.document import Document
from models.graph_edge import GraphEdge
from services.semantic_search import SemanticSearchError, request_graph_links

def _serialize_datetime(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _serialize_graph_document(document: Document) -> dict:
    return {
        "document_id": str(document.id),
        "title": str(document.title or ""),
        "category": str(document.category or ""),
        "tags": [str(tag) for tag in document.tags],
        "summary": str(document.summary or ""),
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


def _upsert_edge(
    *,
    db: Session,
    user_id: str,
    source_id: str,
    target_id: str,
    edge_type: str,
    score: float,
    reason: dict,
) -> bool:
    if not source_id or not target_id or source_id == target_id:
        return False

    if edge_type == "parent_of":
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
                return False
            db.delete(reverse)

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
        return False

    db.add(
        GraphEdge(
            id=str(uuid.uuid4()),
            user_id=str(user_id),
            source_document_id=source_id,
            target_document_id=target_id,
            edge_type=edge_type,
            score=score,
            reason_json=reason_json,
            status="active",
        )
    )
    return True


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
    payload = {
        "user_id": str(user_id),
        "source_document": _serialize_graph_document(source_document),
        "candidate_documents": [_serialize_graph_document(document) for document in candidate_documents],
        "limit": limit or GRAPH_MAX_TOP_K,
        "max_edges": max_edges or GRAPH_MAX_EDGES_PER_DOC,
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
    for item in link_result.get("items") or []:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source") or "")
        target_id = str(item.get("target") or "")
        edge_type = str(item.get("edge_type") or "similar_to")
        was_created = _upsert_edge(
            db=db,
            user_id=str(user_id),
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            score=float(item.get("score") or 0.0),
            reason=item.get("reason") if isinstance(item.get("reason"), dict) else {},
        )
        if source_id and target_id and source_id != target_id:
            edge_keys.append((source_id, target_id, edge_type))
        if was_created:
            created += 1
        else:
            updated += 1

    db.commit()
    return {"deleted": deleted, "created": created, "updated": updated, "skipped": 0, "edge_keys": edge_keys}


def delete_document_edges(*, db: Session, user_id: str, document_id: str) -> int:
    deleted = _delete_incident_edges(db=db, user_id=user_id, document_id=document_id)
    db.commit()
    return deleted
