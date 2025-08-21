from fastapi import (
    APIRouter,
    Depends,
    status,
    UploadFile,
    File,
    HTTPException,
    Response,
)
from src.config import UPLOAD_DIR, MAX_FILE_SIZE
from pathlib import Path
from ..jwt_auth import current_user
from ..db import AsyncSession, get_async_session
from ..models.users import User
from ..models.documents import Document
from ..models.extractions import Extraction
from ..schemas.documents import DocumentResponse
from ..schemas.extractions import (
    DataExtractionResponse,
    DocumentExtractionsResponse,
    AnalyzeExtractionResponse,
)
import uuid
import shutil
import os
import httpx
from typing import Tuple, Dict
from datetime import datetime
from sqlmodel import select
import pandas as pd
from pandas import DataFrame, Series
from textwrap import dedent
from dotenv import load_dotenv
from ..config import settings
import json


# Loading environment variables
load_dotenv()


router = APIRouter(tags=["documents"])
UPLOAD_DIR.mkdir(exist_ok=True)


#### Helper Functions ####


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


def clean_extracted_content(extractions: Dict) -> Tuple[str, str]:
    df = pd.DataFrame([e.data for e in extractions])
    table_preview = df.head(20).to_markdown(index=False)
    json_data = df.where(pd.notna(df), None).to_dict(orient="records")
    json_output = json.dumps(json_data, indent=2)

    print(table_preview)
    return table_preview, json_output


def assemble_data_analysis_prompt(table_preview: str, json_output: str) -> str:

    prompt = dedent(
        f"""
        You are an expert data analyst. Your task is to analyze the provided data table and its statistical summary. Please explain your findings in simple, clear English, as if you were talking to a non-technical manager.
        Here is a preview of the data table:
        {table_preview}
        Here is the json output of the data:
        {json_output}
        Based on the data provided, please answer the following questions:

        1. What are the most important insights?
            Summarize the 2-3 most significant findings or main trends from the data. What is the key story the numbers are telling?
            Or tell that what is the main story or idea of this data/text.
        2. Are there any anomalies?
            Point out any data that looks unusual, surprising, or like an outlier. Briefly explain why it stands out.
            Don't look any kind of anomalies in json ouput data.
        3. What should we do next?
            Recommend 1-2 practical next steps. This could be a business action, a suggestion for deeper analysis, or a data cleaning task.
        """
    )

    return prompt


async def generate_gemini_response(prompt: str) -> str:
    if not settings.gemini_api_key:
        raise ValueError("Gemini url and its needed config have not been set")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                settings.gemini_url,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": settings.gemini_api_key,
                },
                json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
                timeout=60.0,
            )
        except httpx.RequestError as e:
            raise RuntimeError(
                f"There was an error for requesting to Gemini\n Error:{e}"
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"There was an error with Gemini\n Error:{response.text}"
            )

        gemini_result = response.json()
        return gemini_result["candidates"][0]["content"]["parts"][0]["text"]


#### End of Helper Functions ####


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=DocumentResponse)
async def upload_file(
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
            # TODO: implementing background tasks with Celery + RabbitMQ
            pass

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

        # Tables extraction - save actual table extraction
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


@router.post("/analyze/{document_id}", dependencies=[Depends(current_user)], response_model=AnalyzeExtractionResponse)
async def analyze_file_with_ai(
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> AnalyzeExtractionResponse:
    selected_file_query = await session.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    selected_file = selected_file_query.scalar_one_or_none()
    if not selected_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document doesn't exist"
        )

    selected_extraction_query = await session.execute(
        select(Extraction).where(Extraction.document_id == document_id)
    )
    selected_extraction = selected_extraction_query.scalars().all()
    if not selected_extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extractions for this document don't exist",
        )

    table_preview, json_output = clean_extracted_content(
        extractions=selected_extraction
    )
    prompt = assemble_data_analysis_prompt(
        table_preview=table_preview, json_output=json_output
    )
    ai_response = await generate_gemini_response(prompt)

    return AnalyzeExtractionResponse(
        ai_response=ai_response
    )
