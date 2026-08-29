"""
Database engine and session factory.

Provides:
  - Async SQLAlchemy engine (used by the FastAPI app)
  - AsyncSession factory (injected into route handlers via Depends)
  - Base declarative class (imported by all ORM models)
  - get_db() dependency for FastAPI routes
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────
# pool_pre_ping: validates connections before use (handles DB restarts)
# echo: log SQL only in development
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.is_development,
    pool_size=5,
    max_overflow=10,
)

# ── Session factory ───────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Declarative base ──────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this base."""
    pass


# ── FastAPI dependency ────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async database session per request.
    Session is committed on success, rolled back on exception,
    and always closed at the end.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
