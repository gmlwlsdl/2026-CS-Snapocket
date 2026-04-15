import strawberry
from strawberry.types import Info
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.exceptions import UnauthorizedError, NotFoundError, BadUserInputError, InternalServerError
from core.database import get_db
from core.security import jwtAuth
from models.document import Document
from models.document_tag import DocumentTag
from models.tag import Tag
from sqlalchemy import func, or_
from api.apiResponse import ApiResponse

router = APIRouter(prefix="/graph", tags=["graph"])

@strawberry.type
class Node:
    id: str
    title: str
    category: str
    tags: list[str]
    created_at: str
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

        if not user:
            raise UnauthorizedError()

        try:

            # db 조회 후 결과생성
            # 카테고리에 따라 선택적으로 결과값 리턴
            if category:
                nodes = db.query(Document).filter(Document.category == category, Document.deleted_at == None).all()

                if not nodes:
                    raise NotFoundError()

                return nodes
            
            nodes = db.query(Document).all()

            if not nodes:
                raise NotFoundError()

            return nodes
            
        except Exception as e:
            print(e)
            raise InternalServerError()
    
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

        if not user:
            raise UnauthorizedError()

        if not query:
            raise BadUserInputError()
        
        searchQuery = f"%{query}%"
        
        try:

            # db 조회 후 결과생성
            nodes = db.query(Document, DocumentTag, Tag).outerjoin(DocumentTag, Document.id == DocumentTag.document_id).outerjoin(Tag, DocumentTag.tag_id == Tag.id).filter(or_(Document.title.ilike(searchQuery), Document.summary.ilike(searchQuery), Tag.name.ilike(searchQuery)), Document.deleted_at == None).all()

            if not nodes:
                raise NotFoundError()

            return nodes
            
        except Exception as e:
            print(e)
            raise InternalServerError()
    
data = strawberry.Schema(query=Query)

@router.get("/summary", response_model=ApiResponse[dict])
def summary(jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    # db에서 요약데이터 조회
    nodeCount = db.query(func.count(Document.id)).filter(Document.deleted_at == None).scalar()
    tagCount = db.query(func.count(Tag.id)).filter(Document.deleted_at == None).scalar()
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