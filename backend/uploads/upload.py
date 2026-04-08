import os
from fastapi import APIRouter, UploadFile, File
from datetime import datetime

router = APIRouter(prefix="/upload", tags=["upload"])

UPLOAD_DIR = "uploads"

@router.post("")
async def upload_file(file: UploadFile = File(...)):
    # 파일 이름 생성 (중복 방지)
    filename = f"{datetime.now().timestamp()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    # 파일 저장
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    return {
        "filename": filename,
        "original_filename": file.filename,
        "file_path": file_path
    }