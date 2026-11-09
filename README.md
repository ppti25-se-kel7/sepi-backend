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

Dokumentasi API: buka http://localhost:8000/docs

### Mencoba dari HP asli (Flutter)

HP dan laptop harus satu jaringan WiFi. Jalankan server supaya bisa diakses dari perangkat lain:

```
uvicorn app.main:app --reload --host 0.0.0.0
```

Lalu di Flutter pakai alamat `http://<IP-laptop>:8000` (cek IP dengan `ipconfig`). Emulator Android pakai `http://10.0.2.2:8000`. Kalau tidak tersambung, izinkan Python di Windows Firewall.

### Flutter web

Flutter web dari `localhost` (port berapa pun) sudah diizinkan. Untuk alamat lain, isi `CORS_ORIGINS` di `.env`.

## Database

```
alembic upgrade head                 # terapkan migrasi terbaru
python -m scripts.seed_komoditas     # isi data contoh komoditas (sementara)
python -m scripts.seed_wilayah       # isi data wilayah Jabodetabek (sementara)
python -m scripts.seed_harga_dummy   # isi harga palsu 7 hari terakhir (sementara)
```

## Test

```
pip install -r requirements-dev.txt
pytest
```

Test memakai SQLite di memori, tidak menyentuh database Neon.
