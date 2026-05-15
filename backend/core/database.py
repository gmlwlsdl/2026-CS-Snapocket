import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQLALCHEMY_ECHO", "false").strip().lower() == "true",
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def ensure_documents_schema_compatibility():
    inspector = inspect(engine)
    if "documents" not in inspector.get_table_names():
        return

    columns = {col.get("name") for col in inspector.get_columns("documents")}

    with engine.begin() as conn:
        if "doc_id" not in columns:
            conn.execute(text("ALTER TABLE documents ADD COLUMN doc_id VARCHAR(64)"))
        if "raw_text" not in columns:
            conn.execute(text("ALTER TABLE documents ADD COLUMN raw_text TEXT"))
        if "raw" in columns:
            conn.execute(
                text("UPDATE documents SET raw_text = raw WHERE raw_text IS NULL AND raw IS NOT NULL")
            )

    inspector = inspect(engine)
    indexes = inspector.get_indexes("documents")
    unique_constraints = inspector.get_unique_constraints("documents")

    has_doc_id_index = any("doc_id" in (idx.get("column_names") or []) for idx in indexes)
    has_doc_id_unique = any("doc_id" in (uc.get("column_names") or []) for uc in unique_constraints)
    if not has_doc_id_unique:
        has_doc_id_unique = any(
            bool(idx.get("unique")) and "doc_id" in (idx.get("column_names") or [])
            for idx in indexes
        )

    with engine.begin() as conn:
        if not has_doc_id_index:
            conn.execute(text("CREATE INDEX ix_documents_doc_id ON documents (doc_id)"))
        if not has_doc_id_unique:
            conn.execute(text("CREATE UNIQUE INDEX uq_documents_doc_id ON documents (doc_id)"))


def ensure_graph_edges_schema_compatibility():
    from models.graph_edge import GraphEdge

    GraphEdge.__table__.create(bind=engine, checkfirst=True)

    inspector = inspect(engine)
    if "graph_edges" not in inspector.get_table_names():
        return

    columns = {col.get("name") for col in inspector.get_columns("graph_edges")}
    with engine.begin() as conn:
        if "parent_slot_key" not in columns:
            conn.execute(text("ALTER TABLE graph_edges ADD COLUMN parent_slot_key CHAR(36)"))

    db = SessionLocal()
    try:
        from sqlalchemy import func

        duplicate_targets = [
            (user_id, target_id)
            for user_id, target_id in (
                db.query(GraphEdge.user_id, GraphEdge.target_document_id)
                .filter(
                    GraphEdge.edge_type == "parent_of",
                    GraphEdge.status == "active",
                )
                .group_by(GraphEdge.user_id, GraphEdge.target_document_id)
                .having(func.count(GraphEdge.id) > 1)
                .all()
            )
        ]
        for user_id, target_id in duplicate_targets:
            parent_edges = (
                db.query(GraphEdge)
                .filter(
                    GraphEdge.user_id == user_id,
                    GraphEdge.target_document_id == target_id,
                    GraphEdge.edge_type == "parent_of",
                    GraphEdge.status == "active",
                )
                .order_by(GraphEdge.score.desc(), GraphEdge.updated_at.desc(), GraphEdge.created_at.desc())
                .all()
            )
            for edge in parent_edges[1:]:
                db.delete(edge)
        db.commit()
    finally:
        db.close()

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE graph_edges "
                "SET parent_slot_key = target_document_id "
                "WHERE edge_type = 'parent_of' AND status = 'active'"
            )
        )
        conn.execute(
            text(
                "UPDATE graph_edges "
                "SET parent_slot_key = NULL "
                "WHERE edge_type != 'parent_of' OR status != 'active'"
            )
        )

    inspector = inspect(engine)
    indexes = inspector.get_indexes("graph_edges")
    unique_constraints = inspector.get_unique_constraints("graph_edges")
    has_parent_slot_unique = any(
        constraint.get("name") == "uq_graph_edges_user_parent_slot"
        or (constraint.get("column_names") or []) == ["user_id", "parent_slot_key"]
        for constraint in unique_constraints
    ) or any(
        bool(index.get("unique"))
        and (
            index.get("name") == "uq_graph_edges_user_parent_slot"
            or (index.get("column_names") or []) == ["user_id", "parent_slot_key"]
        )
        for index in indexes
    )

    if not has_parent_slot_unique:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_graph_edges_user_parent_slot "
                    "ON graph_edges (user_id, parent_slot_key)"
                )
            )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
