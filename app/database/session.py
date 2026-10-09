from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.models.entities import Base

# Using SQLite with check_same_thread=False for async/FastAPI compatibility
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy import text

def init_db():
    Base.metadata.create_all(bind=engine)
    # Ensure any new columns exist in sqlite if table was already created
    with engine.connect() as conn:
        for col_def in [
            "ALTER TABLE discovered_candidates ADD COLUMN source_url VARCHAR(1000)",
            "ALTER TABLE discovered_candidates ADD COLUMN extracted_predictions JSON"
        ]:
            try:
                conn.execute(text(col_def))
                conn.commit()
            except Exception:
                pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
