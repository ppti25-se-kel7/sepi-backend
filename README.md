# sepi-backend

Backend FastAPI untuk aplikasi SEPI.

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
## Database

```
alembic upgrade head                 # terapkan migrasi terbaru
python -m scripts.seed_komoditas     # isi data contoh komoditas (sementara)
python -m scripts.seed_wilayah       # isi data wilayah Jabodetabek (sementara)
```

## Test

```
pip install -r requirements-dev.txt
pytest
```

Test memakai SQLite di memori, tidak menyentuh database Neon.
