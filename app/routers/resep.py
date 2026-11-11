from urllib.parse import quote

from fastapi import APIRouter
from sqlmodel import col, select

from app.database import SessionDep
from app.errors import AppError, ErrorResponse
from app.models import BahanResep, Komoditas, KomoditasRingkas, Resep, ResepBahan, ResepHarian
from app.routers import prediksi

router = APIRouter(prefix="/recipes", tags=["resep"])


def link_cookpad(nama_resep: str) -> str:
    """Link halaman pencarian Cookpad (Cookpad tidak punya API publik, jadi cukup dibuka di browser)."""
    return f"https://cookpad.com/id/cari/{quote(nama_resep.lower())}"


@router.get(
    "/today",
    response_model=ResepHarian,
    responses={404: {"model": ErrorResponse, "description": "`RESEP_TIDAK_DITEMUKAN`: belum ada data resep"}},
)
def resep_hari_ini(session: SessionDep):
    """Satu resep untuk hari ini. Berganti otomatis tiap hari (WIB), semua user mendapat resep yang sama."""
    semua_resep = session.exec(select(Resep).order_by(col(Resep.id))).all()
    if not semua_resep:
        raise AppError(404, "RESEP_TIDAK_DITEMUKAN", "Belum ada resep")

    tanggal = prediksi.hari_ini()
    resep = semua_resep[tanggal.toordinal() % len(semua_resep)]  # bergiliran: hari berikutnya = resep berikutnya

    bahan = session.exec(
        select(ResepBahan, Komoditas)
        .join(Komoditas, col(Komoditas.id) == col(ResepBahan.komoditas_id))
        .where(ResepBahan.resep_id == resep.id)
        .order_by(col(ResepBahan.jumlah).desc())
    ).all()
    return ResepHarian(
        id=resep.id,
        nama=resep.nama,
        deskripsi=resep.deskripsi,
        porsi=resep.porsi,
        waktu_menit=resep.waktu_menit,
        tanggal=tanggal,
        bahan=[BahanResep(komoditas=KomoditasRingkas.model_validate(k), jumlah=b.jumlah) for b, k in bahan],
        link_cookpad=link_cookpad(resep.nama),
    )
