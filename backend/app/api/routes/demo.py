"""Demo data routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.demo_data_service import seed_demo_data

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.post("/seed")
async def seed_demo(db: AsyncSession = Depends(get_db)) -> dict:
    return await seed_demo_data(db)
