from sqlalchemy import Column, CHAR, String
from core.database import Base

class Tag(Base):
    __tablename__ = "tags"

    id = Column(CHAR(36), primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)