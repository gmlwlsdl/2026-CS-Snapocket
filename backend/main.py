from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import user, document, tag, document_tag, analysis_job

from routers.documents import router as documents_router
from routers.tags import router as tags_router
from routers.upload import router as upload_router

app = FastAPI(title="Snapocket API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(tags_router)
app.include_router(upload_router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Snapocket API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}