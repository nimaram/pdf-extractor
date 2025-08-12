from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, DateTime, Text, Integer, JSON
from fastapi_users_db_sqlalchemy.generics import GUID
from ..dependecies import Base
from datetime import datetime

if TYPE_CHECKING:
    from .users import User
    from .extractions import Extraction


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id"), nullable=False
    )

    # Extraction metadata
    extractions_status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=True
    )
    extraction_started_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime, nullable=True
    )
    extraction_completed_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime, nullable=True
    )
    extraction_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Using JSON for more flexibiltiy
    extraction_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[DateTime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=True
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="documents")
    extractions: Mapped[list["Extraction"]] = relationship(back_populates="document")
    # table_extractions: Mapped[List["TableExtraction"]] = relationship(back_populates="document")
    # diagram_extractions: Mapped[List["DiagramExtraction"]] = relationship(back_populates="document")
    # statistic_extractions: Mapped[List["StatisticExtraction"]] = relationship(back_populates="document")
