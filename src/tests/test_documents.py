import io
import uuid
import pytest
from pathlib import Path
from unittest.mock import patch, Mock
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

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
        ("application/pdf", 200 * 1024 * 1024, "File size exceeds maximum limit"),  # Too large
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
        with patch("pathlib.Path.open", mock_open := Mock()):
            result_path = save_file(mock_file)

    assert result_path.suffix == ".pdf"
    mock_copy.assert_called_once()


# --------------------------
# Endpoint Tests
# --------------------------

@pytest.fixture
def override_current_user(client, test_user):
    from src.jwt_auth import current_user
    
    async def _override():
        return test_user
    
    client.app.dependency_overrides[current_user] = _override
    yield
    client.app.dependency_overrides.clear()


def test_upload_file_success(client, test_user, override_current_user):
    pdf_content = b"%PDF-1.4 test content"
    files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}

    with patch("src.routers.documents.save_file") as mock_save:
        mock_save.return_value = Path("stored.pdf")
        resp = client.post("/", files=files)

    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["filename"] == "test.pdf"
    assert body["user_id"] == str(test_user.id)


def test_upload_file_invalid_type(client, override_current_user):
    files = {"file": ("bad.txt", io.BytesIO(b"bad"), "text/plain")}
    resp = client.post("/", files=files)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_list_documents(client, test_document, override_current_user):
    resp = client.get("/")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert len(body) >= 1
    assert body[0]["id"] == str(test_document.id)


def test_get_document_success(client, test_document, override_current_user):
    resp = client.get(f"/document/{test_document.id}")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["id"] == str(test_document.id)


def test_get_document_not_found(client, override_current_user):
    random_uuid = uuid.uuid4()
    resp = client.get(f"/document/{random_uuid}")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_delete_document_success(client, test_document, override_current_user):
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.unlink"):
        resp = client.delete(f"/remove/{test_document.id}")

    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_delete_document_not_found(client, override_current_user):
    random_uuid = uuid.uuid4()
    resp = client.delete(f"/remove/{random_uuid}")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# --------------------------
# Extraction Endpoints Tests
# --------------------------

def test_extract_data_success(client, test_document, override_current_user):
    fake_extraction_data = {
        "tables": [{
            "table_title": "Table 1",
            "headers": ["A", "B"],
            "rows": [[1, 2]],
            "row_count": 1,
            "column_count": 2,
            "extraction_metadata": {"confidence_score": 0.95}
        }],
        "statistics": [{
            "statistic_type": "sum",
            "statistic_value": 42,
            "statistic_unit": "kg",
            "extraction_metadata": {"confidence_score": 0.85}
        }]
    }

    with patch("src.routers.documents.PDFExtractor") as mock_extractor, \
         patch("pathlib.Path.exists", return_value=True):
        instance = mock_extractor.return_value
        instance.extract_all.return_value = fake_extraction_data

        resp = client.post(f"/extract_data/{test_document.id}")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["extraction_summary"]["tables"] == 1
        assert body["extraction_summary"]["statistics"] == 1


def test_extract_data_document_not_found(client, override_current_user):
    resp = client.post(f"/extract_data/{uuid.uuid4()}")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_extract_data_file_missing(client, test_document, override_current_user):
    with patch("pathlib.Path.exists", return_value=False):
        resp = client.post(f"/extract_data/{test_document.id}")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "File not found" in resp.json()["detail"]


def test_extract_data_extractor_failure(client, test_document, override_current_user):
    with patch("src.routers.documents.PDFExtractor") as mock_extractor, \
         patch("pathlib.Path.exists", return_value=True):
        instance = mock_extractor.return_value
        instance.extract_all.side_effect = RuntimeError("boom")

        resp = client.post(f"/extract_data/{test_document.id}")
    assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Data extraction failed" in resp.json()["detail"]


def test_get_document_extractions_success(client, test_document, db_session, override_current_user):
    extraction1 = Extraction(
        document_id=test_document.id,
        extraction_type="table",
        data={"sample": 1},
        confidence_score=0.9
    )
    extraction2 = Extraction(
        document_id=test_document.id,
        extraction_type="statistic",
        data={"sample": 2},
        confidence_score=0.8
    )
    db_session.add_all([extraction1, extraction2])
    db_session.commit()

    resp = client.get(f"/{test_document.id}/extractions")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "table" in body["extractions"]
    assert "statistic" in body["extractions"]


def test_get_document_extractions_document_not_found(client, override_current_user):
    resp = client.get(f"/{uuid.uuid4()}/extractions")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
