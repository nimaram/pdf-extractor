import uuid
import os
from fastapi import FastAPI, Depends, Request
from fastapi_users import FastAPIUsers
from fastapi.openapi.utils import get_openapi
from .models.users import User, get_user_manager
from .routers import documents
from .jwt_auth import fastapi_users, auth_backend, current_active_user, current_user
from .schemas.users import UserRead, UserCreate
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .dependecies import google_oauth_client
from .middlewares import rate_limiter
from dotenv import load_dotenv

# Loading Environmental Variables
load_dotenv()

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.middleware("http")(rate_limiter)
### Oauth2 Routers ###

app.include_router(
    fastapi_users.get_oauth_router(
        google_oauth_client,
        auth_backend,
        os.getenv("OAUTH2_PASSPHRASE_SECRET"),
        associate_by_email=True,
        is_verified_by_default=True,
    ),
    prefix="/auth/google",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_oauth_associate_router(
        google_oauth_client, UserRead, os.getenv("OAUTH2_PASSPHRASE_SECRET")
    ),
    prefix="/auth/associate/google",
    tags=["auth"],
)

### Oauth2 Routers ###

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
def read_root(request: Request):
    return {"message": "Hello, and thank you for using my app!"}


app.include_router(
    documents.router,
    dependencies=[Depends(current_user)],
    prefix="/docs",
    tags=["documents"],
)
