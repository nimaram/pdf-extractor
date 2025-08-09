from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey
from fastapi_users_db_sqlalchemy.generics import GUID
from ..dependecies import Base

if TYPE_CHECKING:
    from .users import User


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id"), nullable=False
    )
    user: Mapped["User"] = relationship(back_populates="documents")
