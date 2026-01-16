from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
import logging
import os

logger = logging.getLogger(__name__)

# Database URL configuration with pooling optimization
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
if DB_TYPE == "postgresql":
    SQLALCHEMY_DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost/ott_compliance"
    )
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        poolclass=QueuePool,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False
    )
else:
    # SQLite with optimizations
    SQLALCHEMY_DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "sqlite:///./ott_compliance.db?check_same_thread=False"
    )
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 10},
        poolclass=NullPool if DB_TYPE == "sqlite" else QueuePool,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_pool_stats():
    """Get database connection pool statistics"""
    try:
        if hasattr(engine.pool, "size"):
            return {
                "pool_size": getattr(engine.pool, "size", "N/A"),
                "checked_out": getattr(engine.pool, "checkedout", 0)
            }
    except:
        pass
    return {}

def get_db():
    """Database session generator with automatic cleanup and error handling"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()