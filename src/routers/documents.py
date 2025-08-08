from fastapi import APIRouter, status, UploadFile, File, HTTPException
from src.config import UPLOAD_DIR,  MAX_FILE_SIZE
from pathlib import Path
import shutil
import uuid

router = APIRouter(tags=["documents"])
UPLOAD_DIR.mkdir(exist_ok=True)


def save_file(file: UploadFile) -> Path:
    "Save file with a unique name and return its path"
    unique_filename = f"{uuid.uuid4()}{Path(file.filename).suffix}"
    file_path = UPLOAD_DIR / unique_filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


def validate_file(file: UploadFile) -> None:
    """Validate uploaded file meets requirements"""
    if not file.content_type == "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are allowed"
        )

    # Check file size
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset file pointer

    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE // 1_000_000}MB",
        )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...)) -> dict:
    # TODO: background tasks? Celery?
    if not file.content_type == "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are allowed"
        )

    try:
        validate_file(file)
        file_path = save_file(file)

        # background_tasks.add_task(process_file, file_path)
        return {
            "message": "File uploaded successfully",
            "filename": file.filename,
            "stored_filename": file_path.name,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )
