import re
import datetime
import strawberry
from strawberry.types import Info
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.exceptions import UnauthorizedError, NotFoundError, BadUserInputError, InternalServerError
from core.database import get_db
from core.security import jwtAuth
from models.user import User
from models.document import Document
from models.tag import Tag
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload
from api.apiResponse import ApiResponse

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
            
            if start > 0: snippet = "..." + snippet
            if end < len(text): snippet = snippet + "..."
            
            return pattern.sub(r'**\g<0>**', snippet)
        return None
    
    title_match = extract_snippet(document.title)
    if title_match: return title_match

    for tag in document.tags:
        if queryStr.lower() in tag.lower():
            return f"태그: {pattern.sub(r'**\g<0>**', tag)}"

    summary_match = extract_snippet(document.summary)
    if summary_match: return summary_match

    return f"**{queryStr}** 포함됨"

@strawberry.type
class Node:
    id: str
    title: str
    category: str
    tags: list[str]
    created_at: datetime.datetime
    connection_count: int

""" @strawberry.type
class Edge:
    source: str
    target: str
    weight: float """

@strawberry.type
class SearchNode:
    id: str
    title: str
    category: str
    highlight: str

@strawberry.type
class Query:
    @strawberry.field
    def nodes(self, info:Info, category: Optional[str] = None) -> List[Node]:

        db= info.context.get("db")
        user = info.context.get("user")

        userInfo = db.query(User).filter(User.email == user.get("sub")).first()

        if not user:
            raise UnauthorizedError()

        try:

            # db 조회 후 결과생성
            # 카테고리에 따라 선택적으로 결과값 리턴
            subquery = (
                db.query(
                    Document.category, 
                    func.count(Document.id).label("cat_count")
                )
                .filter(
                    Document.user_id == userInfo.id, 
                    Document.deleted_at.is_(None)
                )
                .group_by(Document.category)
                .subquery()
            )

            query = (
                db.query(Document, subquery.c.cat_count)
                .options(joinedload(Document.tag_objects))
                .outerjoin(subquery, Document.category == subquery.c.category)
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
        
        if not results:
            raise NotFoundError()
        
        nodes = []

        for doc, cat_count in results:
            nodes.append(
                Node(
                    id=doc.id,
                    title=doc.title,
                    category=doc.category or "미분류",
                    tags=doc.tags,
                    created_at=doc.created_at,
                    connection_count=cat_count or 0
                )
            )

        return nodes            
    
    """ @strawberry.field
    def edges(self, info:Info) -> List[Edge]:
    
        db= info.context.get("db")
        user = info.context.get("user")

        if not user:
            raise UnauthorizedError()

        # db조회 후 엣지생성


        if False:
            raise NotFoundError()

        edges = []

        return edges """
    
    @strawberry.field
    def searchNodes(self, info:Info, query: str) -> List[SearchNode]:

        db= info.context.get("db")
        user = info.context.get("user")

        userInfo = db.query(User).filter(User.email == user.get("sub")).first()

        if not user:
            raise UnauthorizedError()

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

        if not documents:
            raise NotFoundError()
        
        nodes = []

        for doc in documents:
            nodes.append(
                SearchNode(
                    id=doc.id,
                    title=doc.title,
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
    edgeCount = 0

    return ApiResponse(
        success=True,
        message="조회 성공",
        data={
            "node_count": nodeCount,
            "documents_count": nodeCount,
            "tag_count": tagCount,
            "edge_count": edgeCount
        }
    )