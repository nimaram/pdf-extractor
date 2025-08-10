import pytest
import asyncio
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from pathlib import Path
import tempfile
import shutil
import uuid

from ..main import app
from ..db import get_async_session
from ..models.documents import Document
from ..models.users import User
from ..dependecies import Base
from ..config import UPLOAD_DIR

# Test database URL (in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
async def setup_database():
    """Create tables and clean up after each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session."""
    async with TestingSessionLocal() as session:
        yield session

@pytest.fixture
async def override_get_db(db_session: AsyncSession):
    """Override the database dependency."""
    async def _override_get_db():
        yield db_session
    return _override_get_db

@pytest.fixture
def client(override_get_db) -> TestClient:
    """Create a test client with overridden dependencies."""
    app.dependency_overrides[get_async_session] = override_get_db
    return TestClient(app)

@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_verified=True,
        is_superuser=False
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
async def test_document(db_session: AsyncSession, test_user: User) -> Document:
    """Create a test document."""
    document = Document(
        id=str(uuid.uuid4()),
        filename="test_document.pdf",
        stored_filename="stored_test_document.pdf",
        title="Test Document",
        user_id=test_user.id
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return document

@pytest.fixture
def temp_upload_dir():
    """Create a temporary upload directory for testing."""
    temp_dir = tempfile.mkdtemp()
    original_upload_dir = UPLOAD_DIR
    # Temporarily change the upload directory
    import src.config
    src.config.UPLOAD_DIR = Path(temp_dir)
    yield temp_dir
    # Clean up
    shutil.rmtree(temp_dir)
    src.config.UPLOAD_DIR = original_upload_dir

@pytest.fixture
def mock_current_user(test_user: User):
    """Mock the current_user dependency."""
    from ..jwt_auth import current_user
    
    async def _mock_current_user():
        return test_user
    
    return _mock_current_user