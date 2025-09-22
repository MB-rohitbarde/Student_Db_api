# Student_DB_API

FastAPI application for managing Schools, Teachers, Students, and Student Documents (S3 uploads). Includes JWT auth, structured logging, and comprehensive exception handling.

## Features
- JWT login/refresh, user registration
- CRUD for Schools, Teachers, Students
- Search endpoints with filters and pagination
- Student Documents:
  - Upload file to S3 (max 5 MB)
  - List documents per student (with presigned download URLs)
  - Download latest document for a student (server‑side streaming)
- Centralized exception handling with structured error responses
- Rotating file logs: `logs/app.log`, `logs/error.log`

## Quick start

### 1) Install dependencies
```bash
python -m pip install -r requirements.txt
```

### 2) Configure environment
Create a `.env` in the project root (never commit this):
```ini
# Auth
JWT_SECRET=CHANGE_ME_SUPER_SECRET_KEY
JWT_EXPIRE_MINUTES=15
JWT_REFRESH_DAYS=7

# Database (SQLite by default)
# SQLALCHEMY_DATABASE_URL=sqlite:///./app.db

# AWS / S3
AWS_ACCESS_KEY_ID=YOUR_KEY
AWS_SECRET_ACCESS_KEY=YOUR_SECRET
AWS_REGION=us-east-2
AWS_S3_BUCKET=your-bucket
# Optional for S3-compatible services (e.g., MinIO)
# AWS_S3_ENDPOINT_URL=http://localhost:9000
```

### 3) Run the API
```bash
uvicorn main:app --reload
```
Open Swagger UI: http://127.0.0.1:8000/docs

## Endpoints (selection)

- Auth
  - `POST /auth/login` (form: username, password)
  - `POST /auth/refresh`
  - `POST /auth/register`
- Schools
  - `POST /schools`, `GET /schools`, `GET /schools/{id}`, `PATCH /schools/{id}`, `DELETE /schools/{id}`
- Teachers
  - `POST /teachers`, `GET /teachers`, `GET /teachers/{id}`, `PATCH /teachers/{id}`, `DELETE /teachers/{id}`
  - `GET /teachers/search`
- Students
  - `POST /students`, `GET /students`, `GET /students/{id}`, `PATCH /students/{id}`, `DELETE /students/{id}`
  - `GET /students/search`
- Relationships
  - `POST /students/{student_id}/teachers/{teacher_id}`
  - `GET /students/{student_id}/teachers`
  - `GET /teachers/{teacher_id}/students`
- Student Documents
  - `POST /students/{student_id}/documents` (multipart form: `file`, `document_name`, `document_type`) — max 5 MB
  - `GET /students/{student_id}/documents`
  - `GET /students/{student_id}/download-document` (download latest)

## Logs
- Written to `logs/app.log` (info) and `logs/error.log` (warnings+)
- Request middleware logs each request start/end; exceptions include stack traces

## Exception handling
Centralized handlers return structured JSON:
```json
{
  "error": "Human-readable message",
  "status_code": 400,
  "details": {"field": "name"},
  "path": "/schools/0"
}
```

## Git hygiene
The repository excludes sensitive/local files via `.gitignore`:
- `.env`, `*.env`, `logs/`, `app.db`, `credentials.txt`, caches, IDE folders

## Tests
Run sample tests (if added later):
```bash
pytest -q
```

## License
MIT (add a LICENSE if needed)
