"""FastAPI application entrypoint: wires up routers and startup."""

from fastapi import FastAPI

from database import create_tables
from routers import answers, auth, exercises, llm, schemas

app = FastAPI()


@app.on_event("startup")
async def _startup():
    await create_tables()


app.include_router(auth.router)
app.include_router(schemas.router)
app.include_router(exercises.router)
app.include_router(answers.router)
app.include_router(llm.router)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
