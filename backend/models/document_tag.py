from sqlalchemy import Column, Integer, ForeignKey
from core.database import Base

class DocumentTag(Base):
    __tablename__ = "document_tags"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    tag_id = Column(Integer, ForeignKey("tags.id"))