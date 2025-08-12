from typing import TYPE_CHECKING, Optional, Dict, Any
import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    ForeignKey,
    DateTime,
    Integer,
    JSON,
    Text,
    CheckConstraint,
)
from fastapi_users_db_sqlalchemy.generics import GUID
from ..dependecies import Base

if TYPE_CHECKING:
    from .documents import Document


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    # Extraction type with constraint
    extraction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        info={
            "check": "extraction_type IN ('table', 'diagram', 'statistic', 'text', 'other')"
        },
    )

    confidence_score: Mapped[Optional[float]] = mapped_column(
        JSON, nullable=True
    )  # Stored in data.extraction_metadata

    # All extraction data stored in JSONB for maximum flexibility
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Vector embedding reference (for AI search)
    embedding_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Timestamps
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="extractions")

    # Add constraint for extraction_type
    __table_args__ = (
        CheckConstraint(
            "extraction_type IN ('table', 'diagram', 'statistic', 'text', 'other')",
            name="valid_extraction_type",
        ),
    )
