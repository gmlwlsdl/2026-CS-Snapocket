from sqlalchemy import Column, Integer, ForeignKey, CHAR
from core.database import Base

class DocumentTag(Base):
    __tablename__ = "document_tags"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(CHAR(36), ForeignKey("documents.id"))
    tag_id = Column(CHAR(36), ForeignKey("tags.id"))