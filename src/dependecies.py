from sqlalchemy.orm import DeclarativeBase
from httpx_oauth.clients.google import GoogleOAuth2
import os
from dotenv import load_dotenv

# Loading environment variables
load_dotenv()


# Oauth2
google_oauth_client = GoogleOAuth2(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    scopes=["openid", "email", "profile"],
)


class Base(DeclarativeBase):
    pass
