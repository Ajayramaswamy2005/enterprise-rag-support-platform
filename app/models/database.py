from sqlalchemy import Column, String, Text, DateTime, JSON, create_engine
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from uuid import uuid4
from app.config import settings

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

db_url = settings.postgres_url
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://") and "+psycopg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

# pool_pre_ping recovers from connections dropped by managed Postgres (e.g. Render, Supabase)
engine = create_engine(db_url, future=True, pool_pre_ping=True, connect_args={"connect_timeout": 5})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Could not connect to PostgreSQL database during init_db: %s", e)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
