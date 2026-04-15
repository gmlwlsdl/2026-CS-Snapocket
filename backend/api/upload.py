import os
import uuid
from datetime import datetime
from fastapi import APIRouter, UploadFile, status, File, Form, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from core.security import jwtAuth
from core.database import get_db
from models.user import User
from models.document import Document
from api.apiResponse import ApiResponse

router = APIRouter(prefix="/documents/upload", tags=["upload"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = ["pdf", "png", "jpg", "jpeg", "mp3", "wav", "mp4"]

FILE_TYPE_MAP = {
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "mp3": "audio",
    "wav": "audio",
    "pdf": "document",
    "mp4": "document",
}


@router.post("", status_code = status.HTTP_201_CREATED, response_model=ApiResponse[dict])
async def upload_file(
    file: UploadFile = File(...),
    autoAnalyze: bool = Form(True),
    jwtToken: dict = Depends(jwtAuth),
    db: Session = Depends(get_db),
):
    if not file.filename or "." not in file.filename:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "파일 이름이 올바르지 않습니다.",
                "error_code": "INVALID_FILE_NAME",
            },
        )

    file_ext = file.filename.split(".")[-1].lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "지원하지 않는 파일 형식입니다.",
                "error_code": "UNSUPPORTED_FILE_TYPE",
            },
        )
    
    userName = jwtToken.get("sub")
    userInfo = db.query(User).filter(User.email == userName).first()

    file_type = FILE_TYPE_MAP.get(file_ext, "document")

    unique_name = f"{datetime.now().timestamp()}_{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    status = "processing" if autoAnalyze else "uploaded"

    # auth 붙기 전까지는 임시 user_id 사용
    # 나중에 토큰 기반으로 교체
    new_document = Document(
        user_id=userInfo.id,
        original_filename=file.filename,
        stored_filename=unique_name,
        file_path=file_path,
        file_type=file_type,
        doc_id=None,
        title=file.filename,
        category="memo",
        summary="업로드된 문서",
        raw_text=None,
        status=status
    )

    db.add(new_document)
    db.commit()
    db.refresh(new_document)

    return ApiResponse(
        success=True,
        message="파일 업로드 성공",
        data={
            "document_id": new_document.id,
            "file_url": f"/{file_path}",
            "file_type": file_type,
            "status": status,
        }
    )