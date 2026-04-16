from sqlalchemy import Column, String, Text, Date, DateTime, ForeignKey, CHAR
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(CHAR(36), primary_key=True)
    user_id = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    doc_id = Column(String(64), unique=True, nullable=True, index=True)
    title = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    capture_date = Column(Date, nullable=True)
    summary = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    status = Column(String(50), default="uploaded")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

    tag_objects = relationship("Tag", secondary="document_tags", back_populates="documents")

    @property
    def tags(self) -> list[str]:
        return [tag.name for tag in self.tag_objects]
    
    @property
    def file_url(self) -> str:
        if not self.file_path:
            return ""
        return self.file_path