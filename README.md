# Query Modeling Monorepo

## Structure
- `backend/`: FastAPI Python backend (Dockerized)
- `frontend/`: React + Vite frontend (Node.js)
- `infra/`: Docker Compose for backend and PostgreSQL
- `shared/`: Shared resources (if needed)

## Quick Start

1. **Start backend and database:**
   ```sh
   cd infra
   docker-compose up --build
   ```
2. **Run frontend:**
   ```sh
   cd frontend
   npm install
   npm run dev
   ```

## Authentication
- Register/login as student or teacher.
- After login, main page matches `querymodeelingpage.html`.

## Migrations
- Use Alembic for DB migrations:
   ```sh
   cd backend
   alembic revision --autogenerate -m "init"
   alembic upgrade head
   ```
