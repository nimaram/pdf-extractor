import io
import uuid
import pytest
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock, mock_open
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
import pytest_asyncio
from src.routers.documents import validate_file, save_file
from src.models.documents import Document
from src.models.extractions import Extraction


# --------------------------
# Utility Function Tests
# --------------------------


@pytest.mark.parametrize(
    "content_type,file_size,expected_error",
    [
        ("text/plain", 1024, "Only PDF files are allowed"),
        ("image/jpeg", 1024, "Only PDF files are allowed"),
        (
            "application/pdf",
            200 * 1024 * 1024,
            "File size exceeds maximum limit",
        ),  # Too large
    ],
)
def test_validate_file_invalid_cases(content_type, file_size, expected_error):
    mock_file = Mock()
    mock_file.content_type = content_type
    mock_file.file.seek = Mock()
    mock_file.file.tell.return_value = file_size

    with pytest.raises(HTTPException) as exc:
        validate_file(mock_file)

    assert expected_error in exc.value.detail


def test_validate_file_valid_pdf():
    mock_file = Mock()
    mock_file.content_type = "application/pdf"
    mock_file.file.seek = Mock()
    mock_file.file.tell.return_value = 1024

    validate_file(mock_file)  # Should not raise


def test_save_file_saves_to_path(tmp_path):
    mock_file = Mock()
    mock_file.filename = "test.pdf"
    mock_file.file = io.BytesIO(b"dummy content")

    with patch("shutil.copyfileobj") as mock_copy:
        with patch("pathlib.Path.open", mock_open()) as mocked_open:
            result_path = save_file(mock_file)

    assert result_path.suffix == ".pdf"
    mock_copy.assert_called_once()
    mocked_open.assert_called_once()


# --------------------------
# Endpoint Tests
# --------------------------
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


@pytest_asyncio.fixture
def override_current_user(client, test_user):
    from src.jwt_auth import current_user

    async def _override():
        return test_user

    client.app.dependency_overrides[current_user] = _override
    yield
    client.app.dependency_overrides.clear()


# ------------------------------------------------------------------
# Endpoint tests (still sync because TestClient is sync)
# ------------------------------------------------------------------
def test_upload_file_success(client, test_document, override_current_user):
    pdf_content = b"%PDF-1.4 test content"
    files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}

    with patch("src.routers.documents.save_file") as mock_save:
        mock_save.return_value = Path("stored.pdf")
        resp = client.post("/docs/", files=files)

    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["filename"] == "test.pdf"


def test_list_documents(client, test_document, override_current_user):
    resp = client.get("/docs/")
    assert resp.status_code == status.HTTP_200_OK
    assert any(d["id"] == str(test_document.id) for d in resp.json())


def test_get_document_success(client, test_document, override_current_user):
    resp = client.get(f"/docs/document/{test_document.id}")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["id"] == str(test_document.id)


def test_delete_document_success(client, test_document, override_current_user):
    with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.unlink"):
        resp = client.delete(f"/docs/remove/{test_document.id}")
    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_extract_data_success(client, test_document, override_current_user):
    fake_data = {
        "tables": [
            {
                "table_title": "T1",
                "headers": ["A"],
                "rows": [[1]],
                "row_count": 1,
                "column_count": 1,
                "extraction_metadata": {"confidence_score": 0.9},
            }
        ],
        "statistics": [],
    }
    with (
        patch("src.services.ocr.PDFExtractor") as mock_extractor,
        patch("pathlib.Path.exists", return_value=True),
    ):
        instance = mock_extractor.return_value
        instance.extract_all.return_value = fake_data
        resp = client.post(f"/docs/extract_data/{test_document.id}")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["extraction_summary"]["tables"] == 1


def test_get_document_extractions_success(
    client, test_document, db_session, override_current_user
):
    ext = Extraction(
        document_id=test_document.id,
        extraction_type="table",
        data={"foo": "bar"},
        confidence_score=0.9,
    )
    db_session.add(ext)
    db_session.commit()

    resp = client.get(f"/docs/{test_document.id}/extractions")
    assert resp.status_code == status.HTTP_200_OK
    assert "table" in resp.json()["extractions"]


def test_analyze_file_success(
    client, test_document, db_session, override_current_user
):
    ext = Extraction(
        document_id=test_document.id,
        extraction_type="table",
        data={"foo": "bar"},
        confidence_score=0.9,
    )
    db_session.add(ext)
    db_session.commit()

    with (
        patch("src.routers.documents.clean_extracted_content", return_value=("TABLE", "JSON")),
        patch("src.routers.documents.assemble_data_analysis_prompt", return_value="PROMPT"),
        patch("src.routers.documents.generate_gemini_response", new_callable=AsyncMock, return_value="AI"),
    ):
        resp = client.post(f"/docs/analyze/{test_document.id}")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["ai_response"] == "AI"