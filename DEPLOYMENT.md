# HealthPulse AI: Deployment Guide

## 1. Local Development Run

The fastest way to test the prototype without external dependencies:

```bash
# 1. Install backend dependencies
cd backend
python -m pip install -r requirements.txt

# 2. Seed initial database (creates demo hospitals, doctors, and questionnaires)
python seed.py

# 3. Launch application (serves API and React frontend on port 8000)
python -m uvicorn app.main:app --reload --port 8000
```
Open **`http://localhost:8000`** in your browser.

---

## 2. Docker & Docker Compose Deployment

For containerized deployment with PostgreSQL:

```bash
# Build and run containers
docker-compose up --build
```

### Containers Created:
- **`healthpulse_postgres`**: PostgreSQL 15 database on port 5432.
- **`healthpulse_backend`**: FastAPI application on port 8000. Automatically seeds the database on container start.
- **`healthpulse_frontend`**: Nginx web server serving the frontend on port 3000.

---

## 3. Environment Variables Reference

Configure `.env` in the root or set in your container orchestrator:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///./healthcare_platform.db` |
| `JWT_SECRET` | Secret key for signing JWT tokens | `super-secret-healthcare-prototype-key-38472918` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Session validity in minutes | `1440` (24 hours) |
| `LLM_PROVIDER` | AI provider (`structured_agent`, `gemini`, `openai`) | `structured_agent` |
| `LLM_API_KEY` | Optional API key for external LLM | `None` |
| `VOICE_PROVIDER` | Voice provider (`browser`, `external`) | `browser` |
