"""Login: memeriksa ID token Firebase yang dikirim Flutter di header `Authorization: Bearer <token>`.

Login (Google dll.) dilakukan Flutter langsung ke Firebase. Backend tidak menyimpan password,
cukup memastikan token itu asli, untuk project kita, dan belum kedaluwarsa.
"""

from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select

from app.config import settings
from app.database import SessionDep
from app.errors import AppError
from app.models import Pengguna

# Kunci publik Google untuk mengecek tanda tangan token Firebase.
# Disimpan sementara (cache) 1 jam supaya tidak diunduh di setiap request.
URL_KUNCI_GOOGLE = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
_pengambil_kunci = jwt.PyJWKClient(URL_KUNCI_GOOGLE, cache_jwk_set=True, lifespan=3600)

# auto_error=False: kalau header tidak ada, kita sendiri yang mengirim error berformat seragam.
# Juga memunculkan tombol "Authorize" (gembok) di /docs.
skema_bearer = HTTPBearer(auto_error=False, description="ID token Firebase dari aplikasi Flutter")


def ambil_kunci_publik(token: str):
    """Pilih kunci publik Google yang cocok dengan token (dilihat dari `kid` di kepala token)."""
    return _pengambil_kunci.get_signing_key_from_jwt(token).key


def periksa_token_firebase(token: str) -> dict:
    """Kembalikan isi token kalau valid. Kalau tidak, lempar AppError."""
    project_id = settings.firebase_project_id
    if not project_id:
        raise AppError(503, "LOGIN_BELUM_DIATUR", "Fitur login belum diatur di server")

    try:
        isi = jwt.decode(
            token,
            ambil_kunci_publik(token),
            algorithms=["RS256"],  # Firebase selalu memakai RS256
            audience=project_id,  # token dibuat untuk project kita, bukan project lain
            issuer=f"https://securetoken.google.com/{project_id}",
            options={"require": ["exp", "iat", "sub"]},  # exp = waktu kedaluwarsa, dicek otomatis
        )
    except jwt.PyJWKClientConnectionError:
        raise AppError(503, "LAYANAN_LOGIN_TIDAK_TERSEDIA", "Tidak bisa memeriksa login, coba lagi nanti")
    except jwt.PyJWTError:
        raise AppError(401, "TOKEN_TIDAK_VALID", "Sesi login tidak valid atau sudah habis, silakan login ulang")

    if not isi["sub"]:
        raise AppError(401, "TOKEN_TIDAK_VALID", "Sesi login tidak valid atau sudah habis, silakan login ulang")
    return isi


def get_pengguna(
    session: SessionDep,
    kredensial: Annotated[HTTPAuthorizationCredentials | None, Depends(skema_bearer)],
) -> Pengguna:
    """Dependency untuk endpoint yang wajib login. User baru otomatis dicatat di tabel `pengguna`."""
    if kredensial is None:
        raise AppError(401, "BELUM_LOGIN", "Silakan login terlebih dahulu")
    isi = periksa_token_firebase(kredensial.credentials)

    pengguna = session.exec(select(Pengguna).where(Pengguna.firebase_uid == isi["sub"])).first()
    if pengguna is None:
        pengguna = Pengguna(firebase_uid=isi["sub"])

    # perbarui email & nama kalau berubah di akun Google-nya
    email, nama = isi.get("email"), isi.get("name")
    if pengguna.id is None or (pengguna.email, pengguna.nama) != (email, nama):
        pengguna.email, pengguna.nama = email, nama
        session.add(pengguna)
        session.commit()
        session.refresh(pengguna)
    return pengguna


PenggunaDep = Annotated[Pengguna, Depends(get_pengguna)]
