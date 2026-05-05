import re
import datetime
import strawberry
from strawberry.types import Info
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from core.exceptions import UnauthorizedError, BadUserInputError, InternalServerError
from core.database import get_db
from core.security import jwtAuth
from models.user import User
from models.document import Document
from models.graph_edge import GraphEdge
from models.tag import Tag
from sqlalchemy import func, or_, and_, union_all
from sqlalchemy.orm import aliased, joinedload
from api.apiResponse import ApiResponse
from services.graph_builder import refresh_document_edges

router = APIRouter(prefix="/graph", tags=["graph"])

def makeHighlightSnippet(document: Document, queryStr: str) -> str:
    if not queryStr:
        return ""

    pattern = re.compile(re.escape(queryStr), re.IGNORECASE)

    def extract_snippet(text: str) -> str | None:
        if not text:
            return None
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            snippet = text[start:end]
            
            if start > 0: 
                snippet = "..." + snippet
            if end < len(text): 
                snippet = snippet + "..."
            
            return pattern.sub(r'**\g<0>**', snippet)
        return None
    
    title_match = extract_snippet(document.title)
    if title_match: 
        return title_match

    for tag in document.tags:
        if queryStr.lower() in tag.lower():
            highlighted_tag = pattern.sub(r"**\g<0>**", tag)
            return "태그: " + highlighted_tag


    summary_match = extract_snippet(document.summary)
    if summary_match: 
        return summary_match

    return f"**{queryStr}** 포함됨"

@strawberry.type
class Node:
    id: str
    title: str
    category: str
    tags: list[str]
    created_at: datetime.datetime
    connection_count: int

@strawberry.type
class Edge:
    source: str
    target: str
    weight: float

@strawberry.type
class SearchNode:
    id: str
    title: str
    category: str
    highlight: str


def _require_user_info(info: Info) -> tuple[Session, User]:
    db = info.context.get("db")
    user = info.context.get("user")
    if not user:
        raise UnauthorizedError()

    user_info = db.query(User).filter(User.email == user.get("sub")).first()
    if not user_info:
        raise UnauthorizedError()
    return db, user_info


def _graph_edge_count_subquery(db: Session, user_id: str):
    edge_documents = union_all(
        db.query(GraphEdge.source_document_id.label("document_id"))
        .filter(
            GraphEdge.user_id == user_id,
            GraphEdge.status == "active",
        )
        .statement,
        db.query(GraphEdge.target_document_id.label("document_id"))
        .filter(
            GraphEdge.user_id == user_id,
            GraphEdge.status == "active",
        )
        .statement,
    ).subquery()

    return (
        db.query(
            edge_documents.c.document_id,
            func.count().label("edge_count"),
        )
        .group_by(edge_documents.c.document_id)
        .subquery()
    )

@strawberry.type
class Query:
    @strawberry.field
    def nodes(self, info:Info, category: Optional[str] = None) -> List[Node]:
        db, userInfo = _require_user_info(info)

        try:
            edge_counts = _graph_edge_count_subquery(db, str(userInfo.id))

            query = (
                db.query(Document, edge_counts.c.edge_count)
                .options(joinedload(Document.tag_objects))
                .outerjoin(edge_counts, Document.id == edge_counts.c.document_id)
                .filter(
                    Document.user_id == userInfo.id,
                    Document.deleted_at.is_(None)
                )
            )

            if category:
                query = query.filter(Document.category == category)

            results = query.all()
        except Exception as e:
            print(e)
            raise InternalServerError()

        nodes = []

        for doc, edge_count in results:
            nodes.append(
                Node(
                    id=doc.id,
                    title=doc.title or "",
                    category=doc.category or "미분류",
                    tags=doc.tags,
                    created_at=doc.created_at,
                    connection_count=int(edge_count or 0),
                )
            )

        return nodes

    @strawberry.field
    def edges(self, info:Info, category: Optional[str] = None) -> List[Edge]:
        db, userInfo = _require_user_info(info)
        source_document = aliased(Document)
        target_document = aliased(Document)

        try:
            query = (
                db.query(GraphEdge)
                .join(source_document, GraphEdge.source_document_id == source_document.id)
                .join(target_document, GraphEdge.target_document_id == target_document.id)
                .filter(
                    GraphEdge.user_id == userInfo.id,
                    GraphEdge.status == "active",
                    source_document.deleted_at.is_(None),
                    target_document.deleted_at.is_(None),
                )
            )

            if category:
                query = query.filter(
                    source_document.category == category,
                    target_document.category == category,
                )

            records = query.order_by(GraphEdge.score.desc(), GraphEdge.created_at.desc()).all()
        except Exception as e:
            print(e)
            raise InternalServerError()

        return [
            Edge(
                source=str(record.source_document_id),
                target=str(record.target_document_id),
                weight=float(record.score or 0.0),
            )
            for record in records
        ]

    @strawberry.field
    def searchNodes(self, info:Info, query: str) -> List[SearchNode]:
        db, userInfo = _require_user_info(info)

        if not query:
            raise BadUserInputError()
        
        searchQuery = f"%{query}%"
        
        try:

            # db 조회 후 결과생성
            documents = (
                db.query(Document)
                .options(joinedload(Document.tag_objects))
                .filter(
                    and_(
                        Document.user_id == userInfo.id,
                        Document.deleted_at.is_(None),
                        or_(
                            Document.title.ilike(searchQuery),
                            Document.summary.ilike(searchQuery),
                            Document.tag_objects.any(Tag.name.ilike(searchQuery))
                        )
                    )
                ).all()
            )
            
        except Exception as e:
            print(e)
            raise InternalServerError()
        
        nodes = []

        for doc in documents:
            nodes.append(
                SearchNode(
                    id=doc.id,
                    title=doc.title or "",
                    category=doc.category or "미분류",
                    highlight=makeHighlightSnippet(doc, query)
                )
            )

        return nodes
    
data = strawberry.Schema(query=Query)

@router.get("/summary", response_model=ApiResponse[dict])
def summary(jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    userName = jwtToken.get("sub")
    userInfo = db.query(User).filter(User.email == userName).first()
    if not userInfo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # db에서 요약데이터 조회
    nodeCount = db.query(func.count(Document.id)).filter(Document.user_id == userInfo.id,Document.deleted_at.is_(None)).scalar()
    tagCount = (
        db.query(func.count(func.distinct(Tag.id)))
        .select_from(Document)
        .join(Document.tag_objects)
        .filter(
            Document.user_id == userInfo.id,  
            Document.deleted_at.is_(None)
        )
        .scalar() or 0
    )
    # MVP에서는 0 고도화 후 지원
    edgeCount = (
        db.query(func.count(GraphEdge.id))
        .filter(
            GraphEdge.user_id == userInfo.id,
            GraphEdge.status == "active",
        )
        .scalar() or 0
    )

    return ApiResponse(
        success=True,
        message="조회 성공",
        data={
            "node_count": nodeCount,
            "document_count": nodeCount,
            "documents_count": nodeCount,
            "tag_count": tagCount,
            "edge_count": edgeCount
        }
    )


@router.post("/rebuild", response_model=ApiResponse[dict])
def rebuild_graph(jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):
    userName = jwtToken.get("sub")
    userInfo = db.query(User).filter(User.email == userName).first()
    if not userInfo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    document_ids = [
        str(document_id)
        for (document_id,) in (
            db.query(Document.id)
            .filter(
                Document.user_id == userInfo.id,
                Document.deleted_at.is_(None),
            )
            .all()
        )
    ]

    created = 0
    deleted = 0
    updated = 0
    skipped = 0
    rebuilt_edge_keys: set[tuple[str, str, str]] = set()
    for document_id in document_ids:
        result = refresh_document_edges(
            db=db,
            document_id=document_id,
            user_id=str(userInfo.id),
            delete_existing=False,
        )
        created += int(result.get("created", 0))
        deleted += int(result.get("deleted", 0))
        updated += int(result.get("updated", 0))
        rebuilt_edge_keys.update(
            tuple(item)
            for item in result.get("edge_keys", [])
            if isinstance(item, tuple) and len(item) == 3
        )
        skipped += int(result.get("skipped", 0))
        if result.get("skipped"):
            break

    if skipped == 0:
        stale_edges = db.query(GraphEdge).filter(GraphEdge.user_id == str(userInfo.id)).all()
        for edge in stale_edges:
            key = (str(edge.source_document_id), str(edge.target_document_id), str(edge.edge_type))
            if key not in rebuilt_edge_keys:
                db.delete(edge)
                deleted += 1
        db.commit()

    return ApiResponse(
        success=True,
        message="그래프 재계산 완료",
        data={
            "document_count": len(document_ids),
            "created": created,
            "updated": updated,
            "deleted": deleted,
            "skipped": skipped,
        },
    )
