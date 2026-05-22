from sqlalchemy import CHAR, Column, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from core.database import Base


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_document_id",
            "target_document_id",
            "edge_type",
            name="uq_graph_edges_user_source_target_type",
        ),
        UniqueConstraint(
            "user_id",
            "parent_slot_key",
            name="uq_graph_edges_user_parent_slot",
        ),
        Index("ix_graph_edges_user_status", "user_id", "status"),
        Index("ix_graph_edges_source_document_id", "source_document_id"),
        Index("ix_graph_edges_target_document_id", "target_document_id"),
    )

    id = Column(CHAR(36), primary_key=True)
    user_id = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    source_document_id = Column(CHAR(36), ForeignKey("documents.id"), nullable=False)
    target_document_id = Column(CHAR(36), ForeignKey("documents.id"), nullable=False)
    edge_type = Column(String(32), nullable=False, default="similar_to")
    parent_slot_key = Column(CHAR(36), nullable=True)
    score = Column(Float, nullable=False)
    reason_json = Column(Text, nullable=False, default="{}")
    status = Column(String(16), nullable=False, default="active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
