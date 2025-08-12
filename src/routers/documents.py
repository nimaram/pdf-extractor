from fastapi import (
    APIRouter,
    Depends,
    status,
    UploadFile,
    File,
    HTTPException,
    Form,
    BackgroundTasks,
)
from src.config import UPLOAD_DIR, MAX_FILE_SIZE
from pathlib import Path
from ..jwt_auth import current_user
from ..db import AsyncSession, get_async_session
from ..models.users import User
from ..models.documents import Document
from ..models.extractions import Extraction
from ..schemas.documents import DocumentResponse
from ..schemas.extractions import DataExtractionResponse, DocumentExtractionsResponse
import uuid
import shutil
from datetime import datetime
from sqlmodel import select
from sqlalchemy import select as sa_select

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


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=DocumentResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    start_extracting_after_uploading: bool = False,
    use_ocr: bool = False,
    use_advanced: bool = False,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> DocumentResponse:
    # TODO: background tasks? Celery?
    if not file.content_type == "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are allowed"
        )

    try:
        validate_file(file)
        file_path = save_file(file)

        document = Document(
            filename=file.filename,
            stored_filename=file_path.name,
            user_id=user.id,
        )

        session.add(document)
        await session.commit()

        if start_extracting_after_uploading:
            background_tasks.add_task(
                extract_data_from_document_background,
                document.id,
                user.id,
                use_ocr,
                use_advanced,
            )

        return document

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


@router.get(
    "/", response_model=list[DocumentResponse], dependencies=[Depends(current_user)]
)
async def list_documents(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[Document]:
    result = await session.execute(select(Document).where(Document.user_id == user.id))
    documents = result.scalars().all()
    return documents


@router.delete("/remove/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    result = await session.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    document = result.scalars().first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied",
        )

    # Delete the actual file from disk
    try:
        file_path = UPLOAD_DIR / document.stored_filename
        if file_path.exists():
            file_path.unlink()
        else:
            print(f"Warning: File {file_path} does not exist on disk")
    except Exception as e:
        print(f"Warning: Could not delete file {file_path}: {e}")

    await session.delete(document)
    await session.commit()


@router.get(
    "/document/{document_id}",
    response_model=DocumentResponse,
    dependencies=[Depends(current_user)],
)
async def get_document(
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Document:
    result = await session.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return document


@router.post(
    "/extract_data/{document_id}",
    dependencies=[Depends(current_user)],
    response_model=DataExtractionResponse,
)
async def extract_data_from_document(
    document_id: uuid.UUID,
    use_ocr: bool = False,
    use_advanced: bool = False,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> DataExtractionResponse:

    result = await session.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    try:
        document.extractions_status = "processing"
        document.extraction_started_at = datetime.now()
        await session.commit()

        file_path = UPLOAD_DIR / document.stored_filename

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk"
            )

        from ..services.ocr import PDFExtractor

        extractor = PDFExtractor(str(file_path))

        extraction_data = extractor.extract_all(
            use_ocr=use_ocr, use_advanced=use_advanced
        )

        extractions = []

        # Tables extraction - save actual table data
        if extraction_data.get("tables"):
            for i, table in enumerate(extraction_data["tables"]):
                table_extraction = Extraction(
                    document_id=document.id,
                    extraction_type="table",
                    data={
                        "table_index": i,
                        "table_title": table.get("table_title", f"Table {i + 1}"),
                        "headers": table.get("headers", []),
                        "rows": table.get("rows", []),
                        "row_count": table.get("row_count", 0),
                        "column_count": table.get("column_count", 0),
                        "extraction_metadata": table.get("extraction_metadata", {}),
                    },
                    confidence_score=table.get("extraction_metadata", {}).get(
                        "confidence_score", 0.9
                    ),
                )
                extractions.append(table_extraction)

        # Statistics extraction - save actual statistics data
        if extraction_data.get("statistics"):
            for i, stat in enumerate(extraction_data["statistics"]):
                stats_extraction = Extraction(
                    document_id=document.id,
                    extraction_type="statistic",
                    data={
                        "statistic_index": i,
                        "statistic_type": stat.get("statistic_type", "unknown"),
                        "statistic_value": stat.get("statistic_value"),
                        "statistic_unit": stat.get("statistic_unit"),
                        "statistic_label": stat.get("statistic_label", ""),
                        "context_text": stat.get("context_text", ""),
                        "extraction_metadata": stat.get("extraction_metadata", {}),
                    },
                    confidence_score=stat.get("extraction_metadata", {}).get(
                        "confidence_score", 0.8
                    ),
                )
                extractions.append(stats_extraction)

        for extraction in extractions:
            session.add(extraction)

        document.extractions_status = "completed"
        document.extraction_completed_at = datetime.now()
        document.extraction_summary = {
            "tables_found": len(extraction_data.get("tables", [])),
            "statistics_found": len(extraction_data.get("statistics", [])),
            "ocr_used": use_ocr,
            "advanced_features": use_advanced,
            "extraction_timestamp": datetime.now().isoformat(),
            "total_extractions": len(extractions),
        }

        await session.commit()

        return DataExtractionResponse(
            message="Data extraction completed successfully",
            document_id=document.id,
            extraction_ids=[ext.id for ext in extractions],
            extraction_summary={
                "tables": len(extraction_data.get("tables", [])),
                "statistics": len(extraction_data.get("statistics", [])),
                "ocr_used": use_ocr,
                "advanced_features": use_advanced,
            },
            extraction_data=extraction_data,
        )

    except Exception as e:
        document.extractions_status = "failed"
        document.extraction_error = str(e)
        await session.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data extraction failed: {str(e)}",
        )


@router.get(
    "/{document_id}/extractions",
    dependencies=[Depends(current_user)],
    response_model=DocumentExtractionsResponse,
)
async def get_document_extractions(
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> DocumentExtractionsResponse:

    result = await session.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    result = await session.execute(
        select(Extraction).where(Extraction.document_id == document.id)
    )
    extractions = result.scalars().all()

    # Group extractions by type
    grouped_extractions = {}
    for extraction in extractions:
        extraction_type = extraction.extraction_type
        if extraction_type not in grouped_extractions:
            grouped_extractions[extraction_type] = []

        grouped_extractions[extraction_type].append(
            {
                "id": extraction.id,
                "data": extraction.data,
                "confidence_score": extraction.confidence_score,
                "created_at": (
                    extraction.created_at.isoformat() if extraction.created_at else None
                ),
            }
        )

    return DocumentExtractionsResponse(
        document_id=document.id,
        document_filename=document.filename,
        extraction_status=document.extractions_status,
        extraction_summary=document.extraction_summary,
        extractions=grouped_extractions,
        total_extractions=len(extractions),
    )


async def extract_data_from_document_background(
    document_id: str,
    user_id: uuid.UUID,
    use_ocr: bool = False,
    use_advanced: bool = False,
):
    # This function needs to be updated to work with background tasks
    # For now, we'll need to create a new session and get the user
    # This is a simplified version - in production you might want to use Celery or similar
    from ..db import get_async_session
    from ..models.users import User

    async for session in get_async_session():
        try:
            # Get the user
            user_result = await session.execute(
                sa_select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                print(f"User {user_id} not found for background extraction")
                return

            # Get the document
            doc_result = await session.execute(
                sa_select(Document).where(Document.id == document_id)
            )
            document = doc_result.scalars().first()

            if not document:
                print(f"Document {document_id} not found for background extraction")
                return

            # Call the extraction function
            await extract_data_from_document(
                document_id=uuid.UUID(document_id),
                use_ocr=use_ocr,
                use_advanced=use_advanced,
                user=user,
                session=session,
            )
        except Exception as e:
            print(f"Background extraction failed: {e}")
        finally:
            await session.close()
