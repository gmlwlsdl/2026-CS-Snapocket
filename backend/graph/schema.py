import strawberry
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/graph")

@strawberry.type
class Node:
    id: str
    title: str
    category: str
    tags: list[str]
    created_at: str
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

class GraphSummaryData(BaseModel):
    nodeCount: int
    documentCount: int
    tagCount: int
    edgeCount: int

@strawberry.type
class Query:
    @strawberry.field
    def nodes(self, category: Optional[str] = None) -> List[Node]:

        # db조회 후 노드생성

        nodes = []

        # 카테고리에 따라 선택적으로 결과값 리턴
        if category:
            return
        return nodes
    
    @strawberry.field
    def edges(self) -> List[Edge]:

        # db조회 후 엣지생성

        edges = []

        return edges
    
    @strawberry.field
    def searchNodes(self, query: str) -> List[SearchNode]:
        
        # db 조회 후 결과생성

        nodes = []

        return nodes
    
data = strawberry.Schema(query=Query)

@router.get("/summary")
def summary():

    # db에서 요약데이터 조회

    return {"success": True, "message": "조회 성공", "data": {}}