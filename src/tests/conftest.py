# tests/conftest.py
import os
import tempfile
import uuid
import pytest
import pytest_asyncio
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.main import app
from src.db import Base, get_async_session   
from src.models.users import User
from src.models.documents import Document

# --------------------------------------------------------
# Async in-memory SQLite
# --------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

async_engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
AsyncTestingSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


# --------------------------------------------------------
# Tables & router mount (once)
# --------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _setup_app():
    from src.routers import documents as documents_router
    app.include_router(documents_router.router, prefix="/docs", tags=["documents"])


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncTestingSessionLocal() as session:
        yield session                       

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# --------------------------------------------------------
# 4.  FastAPI TestClient with correct async override
# --------------------------------------------------------
@pytest.fixture(scope="function")
def client(db_session):
    async def _override():
        yield db_session

    app.dependency_overrides[get_async_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --------------------------------------------------------
# 5.  User & Document factories
# --------------------------------------------------------
@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="secret",
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_document(db_session, test_user):
    doc = Document(
        id=uuid.uuid4(),
        filename="dummy.pdf",
        stored_filename="dummy_stored.pdf",
        user_id=test_user.id,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc