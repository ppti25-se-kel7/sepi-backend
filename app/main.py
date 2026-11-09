from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import engine
from app.errors import pasang_penanganan_error
from app.routers import harga, komoditas, wilayah

app = FastAPI(title="Sempol API")
pasang_penanganan_error(app)

# CORS: izin untuk Flutter web memanggil API dari alamat lain (aplikasi Android tidak terpengaruh)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.daftar_cors_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",  # Flutter web di laptop, port acak
    allow_methods=["*"],
    allow_headers=["*"],  # termasuk Authorization untuk token login nanti
)

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
