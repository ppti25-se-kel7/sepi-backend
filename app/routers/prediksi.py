from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlmodel import Session, col, select

from app.database import SessionDep
from app.errors import AppError, ErrorResponse
from app.models import (
    Komoditas,
    KomoditasRingkas,
    PerbandinganPrediksi,
    PrediksiHarga,
    PrediksiPasar,
    TitikPrediksi,
    Wilayah,
    WilayahRingkas,
)

router = APIRouter(prefix="/forecast", tags=["prediksi"])

WIB = timezone(timedelta(hours=7))  # Indonesia tidak memakai jam musim panas, jadi selisihnya tetap


def hari_ini() -> date:
    """Tanggal hari ini di WIB (server di VPS bisa saja memakai jam UTC)."""
    return datetime.now(WIB).date()


def prediksi_ke_depan(
    session: Session, komoditas_id: int, wilayah_id: int, jenis_pasar: str, mulai: date, sampai: date
) -> PrediksiPasar:
    daftar = session.exec(
        select(PrediksiHarga)
        .where(
            PrediksiHarga.komoditas_id == komoditas_id,
            PrediksiHarga.wilayah_id == wilayah_id,
            PrediksiHarga.jenis_pasar == jenis_pasar,
            col(PrediksiHarga.tanggal_prediksi) >= mulai,
            col(PrediksiHarga.tanggal_prediksi) <= sampai,
        )
        .order_by(col(PrediksiHarga.tanggal_prediksi))
    ).all()
    if not daftar:
        return PrediksiPasar(status="belum_tersedia")
    return PrediksiPasar(
        status="tersedia",
        prediksi=[
            TitikPrediksi(
                tanggal=p.tanggal_prediksi,
                harga=p.harga,
                harga_min=p.harga_min,
                harga_max=p.harga_max,
                versi_model=p.versi_model,
            )
            for p in daftar
        ],
    )


@router.get(
    "",
    response_model=PerbandinganPrediksi,
    responses={
        404: {"model": ErrorResponse, "description": "`KOMODITAS_TIDAK_DITEMUKAN` atau `WILAYAH_TIDAK_DITEMUKAN`"},
        422: {"model": ErrorResponse, "description": "`INPUT_TIDAK_VALID`: parameter kurang atau `hari` di luar 1–31"},
    },
)
def prediksi_harga(
    komoditas: str,
    wilayah: str,
    session: SessionDep,
    hari: int = Query(7, ge=1, le=31, description="Berapa hari ke depan, termasuk hari ini"),
):
    """Prediksi harga pasar tradisional vs modern untuk beberapa hari ke depan (mulai hari ini, WIB)."""
    data_komoditas = session.exec(select(Komoditas).where(Komoditas.label == komoditas)).first()
    if data_komoditas is None:
        raise AppError(404, "KOMODITAS_TIDAK_DITEMUKAN", "Komoditas tidak ditemukan")
    data_wilayah = session.exec(select(Wilayah).where(Wilayah.kode == wilayah)).first()
    if data_wilayah is None:
        raise AppError(404, "WILAYAH_TIDAK_DITEMUKAN", "Wilayah tidak ditemukan")

    mulai = hari_ini()
    sampai = mulai + timedelta(days=hari - 1)
    return PerbandinganPrediksi(
        komoditas=KomoditasRingkas.model_validate(data_komoditas),
        wilayah=WilayahRingkas.model_validate(data_wilayah),
        tradisional=prediksi_ke_depan(session, data_komoditas.id, data_wilayah.id, "tradisional", mulai, sampai),
        modern=prediksi_ke_depan(session, data_komoditas.id, data_wilayah.id, "modern", mulai, sampai),
    )
