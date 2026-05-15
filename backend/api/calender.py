from fastapi import APIRouter, Depends
from pydantic import BaseModel
import uuid
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from sqlalchemy import extract
from collections import defaultdict
from datetime import datetime
from core.database import get_db
from core.security import jwtAuth
from models.user import User
from models.document import Document
from api.apiResponse import ApiResponse

router = APIRouter(prefix="/calendar", tags=["calendar"])

class MonthlyTask(BaseModel):
    id : uuid.UUID
    title : str
    category : str | None = None
    file_type : str

class DailyTask(MonthlyTask):
    deadline : datetime | None = None

@router.get("/", response_model=ApiResponse[dict[str, list[MonthlyTask]]])
def getTasks(year: int, month: int, category: str | None = None, jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    userName = jwtToken.get("sub")
    userInfo = db.query(User).filter(User.email == userName).first()

    query = db.query(Document).filter(
        Document.user_id == userInfo.id,
        Document.deleted_at.is_(None),
        extract('year', Document.created_at) == year,
        extract('month', Document.created_at) == month
    )

    if category:
        query = query.filter(Document.category == category)

    documents = query.all()

    documentDict = defaultdict(list)

    for doc in documents:
        date = doc.created_at.date().isoformat() 
        documentDict[date].append(doc)

    return ApiResponse(
        success=True,
        message="월별 문서 조회 성공",
        data=documentDict
    )

@router.get("/day", response_model=ApiResponse[dict[str, list[DailyTask]]])
def getTask(date: str, category: str | None = None, jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    userName = jwtToken.get("sub")
    userInfo = db.query(User).filter(User.email == userName).first()

    query = db.query(Document).filter(
        Document.user_id == userInfo.id,
        Document.deleted_at.is_(None),
        func.date(Document.created_at) == date 
    )

    if category:
        query = query.filter(Document.category == category)

    documents = query.all()

    documentDict = {"items" : documents}

    return ApiResponse(
        success=True,
        message="해당 일자 문서 조회 성공",
        data=documentDict
    )