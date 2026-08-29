"""Background ingestion worker entry point."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ingest_service import run_ingestion


async def run_once(db: AsyncSession) -> dict:
    return await run_ingestion(db)
