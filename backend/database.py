"""Async SQLAlchemy engine, session factory, and DB dependencies."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from models import Base

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    """Create all tables on startup (registered as a FastAPI startup handler)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
