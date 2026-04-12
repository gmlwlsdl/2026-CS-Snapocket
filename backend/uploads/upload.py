import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from datetime import datetime

router = APIRouter(prefix="/documents/upload", tags=["upload"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    autoAnalyze: bool = Form(True) 
):
    allowed_extensions = ["pdf", "png", "jpg", "jpeg", "mp3", "wav", "mp4"]
    file_ext = file.filename.split('.')[-1].lower()
    
    if file_ext not in allowed_extensions:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "지원하지 않는 파일 형식입니다.",
                "error_code": "UNSUPPORTED_FILE_TYPE"
            }
        )

    if file_ext in ["png", "jpg", "jpeg"]:
        file_type = "image"
    elif file_ext in ["mp3", "wav"]:
        file_type = "audio"
    else:
        file_type = "document"

    document_id = str(uuid.uuid4())
    filename = f"{datetime.now().timestamp()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    status = "processing" if autoAnalyze else "uploaded"

    # TODO: DB에 Document 정보 저장 로직 추가 (document_id, file_path 등)

   
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": "파일 업로드 성공",
            "data": {
                "document_id": document_id,
                "file_url": f"/{file_path}",
                "file_type": file_type,
                "status": status
            }
        }
    )