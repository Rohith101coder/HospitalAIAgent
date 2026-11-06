import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

Base = declarative_base()


def get_engine():
    """Create SQLAlchemy engine with appropriate connection parameters."""
    connect_args = {}
    ca_path = None
    if settings.DB_SSL_CA and os.path.exists(settings.DB_SSL_CA):
        ca_path = settings.DB_SSL_CA
    elif "tidbcloud.com" in settings.DB_HOST or settings.DB_PORT == 4000:
        import certifi
        ca_path = certifi.where()

    if ca_path:
        connect_args["ssl"] = {
            "ca": ca_path,
            "check_hostname": True,
        }

    if settings.DATABASE_URL:
        # Custom or SQLite URL for testing
        is_sqlite = settings.DATABASE_URL.startswith("sqlite")
        if is_sqlite:
            connect_args = {"check_same_thread": False}
        return create_engine(
            settings.DATABASE_URL,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=10,
            max_overflow=20,
        )

    # Build MySQL / TiDB Cloud URL safely
    db_url = URL.create(
        drivername="mysql+pymysql",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD if settings.DB_PASSWORD else None,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        query={"charset": "utf8mb4"},
    )

    return create_engine(
        db_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=10,
        max_overflow=20,
    )


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a request-scoped database session and guarantees cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

