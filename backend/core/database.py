from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from core.config import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=True)
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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
