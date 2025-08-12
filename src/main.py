import uuid
from fastapi import FastAPI, Depends

from .models.users import User, get_user_manager
from .routers import documents
from .jwt_auth import fastapi_users, auth_backend, current_active_user, current_user
from fastapi_users import FastAPIUsers
from .schemas.users import UserRead, UserCreate
from fastapi.openapi.utils import get_openapi


app = FastAPI()


app.include_router(
    documents.router,
    dependencies=[Depends(current_user)],
    prefix="/docs",
    tags=["documents"],
)


app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)

app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)


@app.get("/")
def read_root():
    return {"message": "Hello, and thank you for using my app!"}


# # Authorize button in swagger docs settings
# def custom_openapi():
#     if app.openapi_schema:
#         return app.openapi_schema
#     openapi_schema = get_openapi(
#         title="My API",
#         version="1.0.0",
#         description="Custom auth example",
#         routes=app.routes,
#     )
#     openapi_schema["components"]["securitySchemes"]["JWTBearer"] = {
#         "type": "http",
#         "scheme": "bearer",
#         "bearerFormat": "JWT",
#     }
#     app.openapi_schema = openapi_schema
#     return app.openapi_schema


# app.openapi = custom_openapi
