# Query Modeling Monorepo

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
- Register/login as student or teacher.

## Migrations
- Use Alembic for DB migrations:
   ```sh
   cd backend
   alembic revision --autogenerate -m "init"
   alembic upgrade head
   ```
