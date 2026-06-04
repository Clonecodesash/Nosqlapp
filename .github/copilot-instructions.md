# Copilot Workspace Instructions

## Monorepo Structure
- `backend/`: FastAPI backend (Python, Docker)
- `frontend/`: React (Node.js, Vite)
- `infra/`: Docker Compose for backend and PostgreSQL
- `shared/`: Shared code/resources

## Build & Run
- Use `docker-compose` in `infra/` to run backend and DB
- Use `npm run dev` in `frontend/` for local frontend

## Conventions
- Use Alembic for DB migrations
- JWT-based authentication for student/teacher roles
- Link to `README.md` for setup and migration details

## Anti-patterns
- Do not duplicate documentation—link to `README.md` or code
- Do not hardcode secrets in code (use env vars)

## Example Prompts
- "Add a new API endpoint for teachers only."
- "Update the frontend to show student-specific content."
- "How do I run migrations?"
