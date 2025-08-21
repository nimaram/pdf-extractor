from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from collections.abc import AsyncGenerator
from .dependecies import Base
import os
from dotenv import load_dotenv

# Loading environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
        
        
# Synchronous engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # for SQLite, safe for in-memory tests
)

# Synchronous session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# Dependency for FastAPI (sync)
def get_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()        