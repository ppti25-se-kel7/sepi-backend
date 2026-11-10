from fastapi import APIRouter

from app.auth import PenggunaDep
from app.errors import ErrorResponse
from app.models import PenggunaPublic

router = APIRouter(prefix="/pengguna", tags=["pengguna"])


@router.get(
    "/saya",
    response_model=PenggunaPublic,
    responses={
        401: {"model": ErrorResponse, "description": "`BELUM_LOGIN` atau `TOKEN_TIDAK_VALID` (login ulang)"},
        503: {"model": ErrorResponse, "description": "`LOGIN_BELUM_DIATUR` atau `LAYANAN_LOGIN_TIDAK_TERSEDIA`"},
    },
)
def profil_saya(pengguna: PenggunaDep):
    """Data user yang sedang login. Wajib kirim header `Authorization: Bearer <ID token Firebase>`."""
    return pengguna
