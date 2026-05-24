from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.sql import func, and_
from sqlalchemy.orm import Session
from core.security import jwtAuth
from core.database import get_db
from models.user import User
from models.document import Document
from models.document_tag import DocumentTag
from models.tag import Tag
import uuid
from api.apiResponse import ApiResponse

router = APIRouter(tags=["tags"])

class Tags(BaseModel):
    id: uuid.UUID
    name: str
    count: int | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get("/tags", response_model=ApiResponse[list[Tags]])
def getTags(keyword: str | None = None, jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    userName = jwtToken.get("sub")
    userInfo = db.query(User).filter(User.email == userName).first()

    if keyword:
        searchKeyword = f"%{keyword}%"
        tags = db.query(Tag.id, Tag.name, func.count(Document.id).label("count")).outerjoin(DocumentTag, Tag.id == DocumentTag.tag_id).outerjoin(Document, and_(DocumentTag.document_id == Document.id, Document.user_id == userInfo.id, Document.deleted_at.is_(None))).filter(Tag.name.ilike(searchKeyword)).group_by(Tag.id).all()
    else:
        tags = db.query(Tag.id, Tag.name, func.count(Document.id).label("count")).outerjoin(DocumentTag, Tag.id == DocumentTag.tag_id).outerjoin(Document, and_(DocumentTag.document_id == Document.id, Document.user_id == userInfo.id, Document.deleted_at.is_(None))).group_by(Tag.id).all()



    return ApiResponse(
        success=True,
        message="태그 조회 성공",
        data=tags
    )

@router.post("/documents/{document_id}/tags", response_model=ApiResponse[list])
def addTags(document_id: str, tags: list[str], jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    existingTags = db.query(Tag).filter(Tag.name.in_(tags)).all()
    
    existingTagDict = {tag.name: tag for tag in existingTags}

    linkedTagRows = (
        db.query(DocumentTag.tag_id)
        .filter(DocumentTag.document_id == document_id)
        .all()
    )
    linkedTagSet = {row[0] for row in linkedTagRows}

    tagData = []

    # 입력받은 태그들을 하나씩 순회하며 처리
    for tagName in tags:
        
        # 태그가 DB에 아예 없으면 새로 만들기
        if tagName not in existingTagDict:
            newTag = Tag(id=str(uuid.uuid4()), name=tagName)
            db.add(newTag)

            db.flush()
            
            # 방금 만든 태그를 딕셔너리에 넣어둬서 바로 쓸 수 있게 함
            existingTagDict[tagName] = newTag 
            targetTag = newTag
        else:
            targetTag = existingTagDict[tagName]

        # 문서에 아직 안 달려있으면 연결
        if targetTag.id not in linkedTagSet:
            new_document_tag = DocumentTag(document_id=document_id, tag_id=targetTag.id)
            db.add(new_document_tag)
            
            # 중복으로 들어오는 경우 방지
            linkedTagSet.add(targetTag.id) 
            
            # 새롭게 추가된 태그만 응답 데이터에 담기
            tagData.append({"id": targetTag.id, "name": tagName})

    db.commit()

    return ApiResponse(
        success=True,
        message="태그 추가 성공",
        data = tagData
    )

@router.patch("/documents/{document_id}/tags", response_model=ApiResponse[list])
def changeTags(document_id: str, tags: list[str], jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    existing_tags = db.query(Tag).filter(Tag.name.in_(tags)).all()

    existing_tag_dict = {tag.name: tag for tag in existing_tags}

    db.query(DocumentTag).filter(DocumentTag.document_id == document_id).delete()

    tagData = []

    for tag_name in tags:
        if tag_name not in existing_tag_dict:
            new_tag = Tag(id=str(uuid.uuid4()), name=tag_name)
            db.add(new_tag)

            db.flush()

            existing_tag_dict[tag_name] = new_tag 
            target_tag = new_tag

        else:
            target_tag = existing_tag_dict[tag_name]

        new_document_tag = DocumentTag(document_id=document_id, tag_id=target_tag.id)
        db.add(new_document_tag)
        tagData.append({"id": target_tag.id, "name": tag_name})

    db.commit()

    return ApiResponse(
        success=True,
        message="태그 교체 성공",
        data=tagData
    )

@router.delete("/documents/{document_id}/tags/{tag_id}", response_model=ApiResponse[None])
def deleteTag(document_id: str, tag_id: str, jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    deletedCount = db.query(DocumentTag).filter(DocumentTag.document_id == document_id, DocumentTag.tag_id == tag_id).delete()
    db.commit()

    if deletedCount == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "message": "해당 태그가 문서에 존재하지 않습니다.",
                "error_code": "TAG_NOT_FOUND"
            }
        )

    return ApiResponse(
        success=True,
        message="태그 삭제 성공",
        data=None
    )