import os
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from models.document import Document

router = APIRouter(prefix="/upload", tags=["upload"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

CATEGORIES = ["lecture", "assignment", "notice", "receipt", "memo"]


@router.post("")
async def upload_file(
    user_id: int = Form(...),
    title: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if category not in CATEGORIES:
        return {"error": f"잘못된 category 값입니다: {category}"}

    filename = f"{datetime.now().timestamp()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    ext = os.path.splitext(file.filename)[1].lower().replace(".", "")

    new_document = Document(
        user_id=user_id,
        original_filename=file.filename,
        stored_filename=filename,
        file_path=file_path,
        file_type=ext,
        title=title,
        category=category,
        summary="업로드된 문서",
        status="uploaded",
    )

    db.add(new_document)
    db.commit()
    db.refresh(new_document)

    return {
        "message": "파일 업로드 성공",
        "document_id": new_document.id,
        "original_filename": file.filename,
        "stored_filename": filename,
        "file_path": file_path,
        "category": category,
        "status": new_document.status,
    }