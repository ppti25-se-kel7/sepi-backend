# sempol-backend

Backend FastAPI untuk aplikasi Sempol.

## Menjalankan di lokal

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Isi `DATABASE_URL` di `.env` dengan connection string Neon, lalu:

```
uvicorn app.main:app --reload
```

- Cek kesehatan: http://localhost:8000/health
- Dokumentasi API: http://localhost:8000/docs

## Database

```
alembic upgrade head                 # terapkan migrasi terbaru
python -m scripts.seed_komoditas     # isi data contoh komoditas (sementara)
```

## Test

```
pip install -r requirements-dev.txt
pytest
```

Test memakai SQLite di memori, tidak menyentuh database Neon.
