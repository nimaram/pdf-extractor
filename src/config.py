from pathlib import Path


# Base directory(src)
BASE_DIR = Path(__file__).parent

# Document router configuration
UPLOAD_DIR = BASE_DIR / "UploadedDocs"
ALLOWED_EXTENSIONS = [".pdf"]
MAX_FILE_SIZE = 50_000_000  # 50MB in bytes


