# Base image
FROM python:3.11-slim


# Set work directory
WORKDIR /app


# Install system dependencies
RUN apt-get update && apt-get install -y \
build-essential \
libpq-dev \
&& rm -rf /var/lib/apt/lists/*


# Copy dependency files
COPY pyproject.toml requirements.txt ./


# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir -r requirements.txt


# Copy source code
COPY src/ ./src


# Create uploads directory
RUN mkdir -p /app/src/UploadedDocs


# Expose port
EXPOSE 8000


# Start app
CMD uvicorn src.main:app --host 0.0.0.0 --port 8000