from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.errors import pasang_penanganan_error
from app.routers import harga, komoditas, wilayah

app = FastAPI(title="Sempol API")
pasang_penanganan_error(app)
app.include_router(komoditas.router)
app.include_router(wilayah.router)
app.include_router(harga.router)


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
