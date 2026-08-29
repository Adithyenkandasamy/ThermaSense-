"""Database compatibility module for the clean backend layout."""

from app.database import AsyncSessionLocal, Base, engine, get_db

__all__ = ["AsyncSessionLocal", "Base", "engine", "get_db"]
