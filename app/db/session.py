from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

import os
from sqlalchemy.pool import NullPool

# Replace 'postgres://' with 'postgresql://' if needed for SQLAlchemy
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

is_serverless = os.environ.get("VERCEL") == "1" or settings.ENVIRONMENT == "production"

if is_serverless:
    engine = create_engine(db_url, poolclass=NullPool)
else:
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
