from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

# Loading environmental variables
load_dotenv()


class Settings(BaseSettings):
    # TODO: move other setting variables to this class
    gemini_url: Optional[str] = Field(env="GEMINI_URL")
    gemini_api_key: Optional[str] = Field(env="GEMINI_API_KEY")


# Base directory(src)
BASE_DIR = Path(__file__).parent

# Document router configuration
UPLOAD_DIR = BASE_DIR / "UploadedDocs"
ALLOWED_EXTENSIONS = [".pdf"]
MAX_FILE_SIZE = 8_000_000  # 8MB in bytes


settings = Settings()
