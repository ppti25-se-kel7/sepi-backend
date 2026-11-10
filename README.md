# sepi-backend

Backend FastAPI untuk aplikasi SEPI.

## Menjalankan di lokal

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Isi `DATABASE_URL` di `.env` dengan connection string Neon (dan `FIREBASE_PROJECT_ID` untuk fitur login), lalu:

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
python -m scripts.seed_wilayah       # isi 86 kab/kota yang dicakup PIHPS (kode Kemendagri)
python -m scripts.seed_harga_dummy   # isi harga palsu 7 hari terakhir (sementara)
python -m scripts.seed_prediksi_dummy  # isi prediksi palsu 7 hari ke depan (sementara)
```

### Impor prediksi harga (dari model prediksi)

```
python -m scripts.impor_prediksi path/ke/prediksi.csv
```

Format CSV (harga_min & harga_max boleh kosong):

```
komoditas,wilayah,jenis_pasar,tanggal_prediksi,harga,harga_min,harga_max,versi_model
beras,32.01,tradisional,2026-11-11,15200,14800,15600,v1
```

Kalau ada baris yang salah, tidak ada yang disimpan dan semua kesalahan ditampilkan.

## Test

```
pip install -r requirements-dev.txt
pytest
```

Test memakai SQLite di memori, tidak menyentuh database Neon.
