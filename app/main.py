from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.routers import komoditas

app = FastAPI(title="Sempol API")
app.include_router(komoditas.router)


@app.get("/health")
def health():
    """Cek apakah server hidup dan database bisa dihubungi."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "error"
    return {"status": "ok", "database": database}
