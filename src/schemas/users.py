from pydantic import Field
import uuid
from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    password: str = Field(..., min_length=8)


class UserUpdate(schemas.BaseUserUpdate):
    pass
