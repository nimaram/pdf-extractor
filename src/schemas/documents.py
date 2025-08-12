from pydantic import BaseModel
from typing import Optional
import uuid


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    stored_filename: str
    title: Optional[str]
    user_id: uuid.UUID

    class Config:
        from_attributes = True
