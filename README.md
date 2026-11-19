# Aggregate Lab

## Structure
- `backend/`: FastAPI Python backend (Dockerized)
- `frontend/`: React + Vite frontend (Node.js)
- `infra/`: Docker Compose for backend and PostgreSQL
- `shared/`: Shared resources (if needed)

## Quick Start

1. **Start  project:**
   ```sh
   cd infra
   docker-compose up --build
   ```

## Authentication
- Anyone can register as a student. Teacher registration requires a matching
  `TEACHER_INVITE_CODE` set in `backend/.env`; keep this value secret and share
  it only with trusted teachers.

## Migrations
- Use Alembic for DB migrations:
   ```sh
   cd backend
   alembic revision --autogenerate -m "init"
   alembic upgrade head
   ```
