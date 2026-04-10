from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from core.database import Base

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    raw_result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)