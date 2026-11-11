from fastapi import APIRouter
from sqlmodel import Session, col, select

from app.database import SessionDep
from app.errors import AppError, ErrorResponse
from app.models import (
    HargaHarian,
    HargaPasar,
    Komoditas,
    KomoditasRingkas,
    PerbandinganHarga,
    Wilayah,
    WilayahRingkas,
)

router = APIRouter(prefix="/prices", tags=["harga"])


def harga_terbaru(session: Session, komoditas_id: int, wilayah_id: int, jenis_pasar: str) -> HargaPasar:
    """Harga paling baru untuk satu jenis pasar. Kalau belum ada, harganya null (bukan 0)."""
    harga = session.exec(
        select(HargaHarian)
        .where(
            HargaHarian.komoditas_id == komoditas_id,
            HargaHarian.wilayah_id == wilayah_id,
            HargaHarian.jenis_pasar == jenis_pasar,
        )
        .order_by(col(HargaHarian.tanggal).desc())
    ).first()
    if harga is None:
        return HargaPasar(status="belum_tersedia")
    return HargaPasar(status="tersedia", harga=harga.harga, tanggal=harga.tanggal, sumber=harga.sumber)


@router.get(
    "",
    response_model=PerbandinganHarga,
    responses={
        404: {"model": ErrorResponse, "description": "`KOMODITAS_TIDAK_DITEMUKAN` atau `WILAYAH_TIDAK_DITEMUKAN`"},
        422: {"model": ErrorResponse, "description": "`INPUT_TIDAK_VALID`: parameter kurang"},
    },
)
def perbandingan_harga(komoditas: str, wilayah: str, session: SessionDep):
    """Harga terbaru pasar tradisional vs modern. `komoditas` = label (mis. `beras`), `wilayah` = kode (mis. `32.71`)."""
    data_komoditas = session.exec(select(Komoditas).where(Komoditas.label == komoditas)).first()
    if data_komoditas is None:
        raise AppError(404, "KOMODITAS_TIDAK_DITEMUKAN", "Komoditas tidak ditemukan")
    data_wilayah = session.exec(select(Wilayah).where(Wilayah.kode == wilayah)).first()
    if data_wilayah is None:
        raise AppError(404, "WILAYAH_TIDAK_DITEMUKAN", "Wilayah tidak ditemukan")

    return PerbandinganHarga(
        komoditas=KomoditasRingkas.model_validate(data_komoditas),
        wilayah=WilayahRingkas.model_validate(data_wilayah),
        tradisional=harga_terbaru(session, data_komoditas.id, data_wilayah.id, "tradisional"),
        modern=harga_terbaru(session, data_komoditas.id, data_wilayah.id, "modern"),
    )
