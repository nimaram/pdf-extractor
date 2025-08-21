# PDF Analytics AI

A FastAPI-based web application that allows users to authenticate with JWT, upload PDF files, extract tables and statistics, and use AI (Gemini LLM) to analyze those statistics. Built with PostgreSQL for data storage and designed for seamless AI-driven insights.

---

## Features

* **JWT Authentication**: Secure user login and registration.
* **PDF Upload**: Users can upload PDF files for analysis.
* **Table & Statistics Extraction**: Automatically extract tables and relevant statistics from PDFs.
* **AI Analysis**: Utilize Gemini LLM to analyze extracted statistics.
* **FastAPI + Uvicorn**: High-performance API backend.
* **PostgreSQL Database**: Persistent and reliable data storage.

---

## Tech Stack

* **Backend**: FastAPI
* **ASGI Server**: Uvicorn
* **Database**: PostgreSQL
* **AI**: Gemini LLM (via API key)
* **Migrations**: Alembic
* **Containerization**: Docker & Docker Compose

---

## Project Structure

```
.
├── src/                  # Application source code
│   ├── models/           # Database models
│   ├── routers/          # API routes
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic and PDF/AI services
│   ├── tests/            # Unit and integration tests
│   ├── UploadedDocs/     # Uploaded PDF files
│   ├── client.py         # Gemini API client
│   ├── config.py         # Configuration and environment loading
│   ├── db.py             # Database connection
│   ├── dependecies.py    # FastAPI dependencies
│   ├── jwt_auth.py       # JWT authentication utilities
│   ├── main.py           # FastAPI app entrypoint
│   └── __init__.py       # Package initializer
├── migrations/           # Database migrations
├── .venv/                # Python virtual environment
├── .env                  # Environment variables
├── Dockerfile            # Docker setup
├── compose.yaml          # Docker Compose configuration
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project configuration
├── README.Docker.md      # Docker-specific instructions
└── test_types.py         # Sample tests
```

---

## Getting Started

### Prerequisites

* Python 3.11+
* PostgreSQL
* Docker (optional but recommended)
* Gemini API Key

### Installation

1. Clone the repository:

```bash
git clone <repo-url>
cd <project-folder>
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables:

* Copy `.env-sample` to `.env` and fill in your settings (database URL, Gemini API key, JWT secret, etc.).

5. Run migrations:

```bash
alembic upgrade head
```

6. Start the application:

```bash
uvicorn src.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

---

## Usage

* **Register/Login**: Use JWT authentication endpoints to create an account or log in.
* **Upload PDF**: POST your PDF files to the `/upload` endpoint.
* **Extract & Analyze**: The app extracts tables/statistics and sends them to Gemini LLM for analysis.
* **View Results**: Retrieve AI-analyzed insights via API responses.

---

## Docker Usage

Build and run the project using Docker:

```bash
docker-compose up --build
```

---

## Environment Variables

| Variable         | Description                       |
| ---------------- | --------------------------------- |
| `DATABASE_URL`   | PostgreSQL connection URL         |
| `GEMINI_API_KEY` | API key for Gemini LLM            |
| `JWT_SECRET`     | Secret key for JWT authentication |
| `UPLOAD_DIR`     | Directory to store uploaded PDFs  |

---

## License

This project is licensed under the MIT License.

---

## Future Improvements

* Add user roles and permissions.
* Support batch PDF uploads.
* Enhance AI analysis with visualization dashboards.
* Add frontend interface for better user experience.
