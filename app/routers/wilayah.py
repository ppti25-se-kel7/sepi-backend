from datetime import timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Annotated

from fastapi import APIRouter, Query
from sqlmodel import and_, col, func, or_, select

from app.database import SessionDep
from app.errors import AppError, ErrorResponse
from app.models import (
    HargaHarian,
    Komoditas,
    KomoditasRingkas,
    PrediksiHarga,
    RingkasanKomoditas,
    RingkasanPasar,
    RingkasanWilayah,
    Wilayah,
    WilayahPublic,
    WilayahRingkas,
    WilayahTerdekat,
)
from app.routers import prediksi

router = APIRouter(prefix="/wilayah", tags=["wilayah"])

RADIUS_BUMI_KM = 6371


def hitung_jarak_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Jarak garis lurus dua titik di permukaan bumi (rumus Haversine)."""
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * RADIUS_BUMI_KM * asin(sqrt(a))


@router.get("", response_model=list[WilayahPublic])
def daftar_wilayah(session: SessionDep, q: str | None = None):
    """Daftar kab/kota yang dicakup PIHPS, urut provinsi lalu nama. Isi `q` untuk mencari di nama atau provinsi."""
    query = select(Wilayah).order_by(Wilayah.provinsi, Wilayah.nama)
    if q:
        pola = f"%{q.strip()}%"
        query = query.where(or_(col(Wilayah.nama).ilike(pola), col(Wilayah.provinsi).ilike(pola)))
    return session.exec(query).all()


@router.get(
    "/terdekat",
    response_model=WilayahTerdekat,
    responses={
        404: {"model": ErrorResponse, "description": "`WILAYAH_TIDAK_DITEMUKAN`: belum ada data wilayah"},
        422: {"model": ErrorResponse, "description": "`INPUT_TIDAK_VALID`: lat/lng kosong atau di luar batas"},
    },
)
def wilayah_terdekat(
    session: SessionDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
):
    """Wilayah (kota sampel PIHPS) yang titik pusatnya paling dekat dengan koordinat user (dari GPS HP).

    Daerah yang tidak punya data harga sendiri diarahkan ke kota terdekat, mis. Sentul → Kota Bogor.
    `jarak_km` bisa ditampilkan Flutter sebagai keterangan ("harga Kota Bogor, ±8 km dari lokasimu").
    """
    semua_wilayah = session.exec(select(Wilayah)).all()
    if not semua_wilayah:
        raise AppError(404, "WILAYAH_TIDAK_DITEMUKAN", "Belum ada data wilayah")
    terdekat = min(semua_wilayah, key=lambda w: hitung_jarak_km(lat, lng, w.lat, w.lng))
    jarak = hitung_jarak_km(lat, lng, terdekat.lat, terdekat.lng)
    return WilayahTerdekat(**terdekat.model_dump(), jarak_km=round(jarak, 2))


BATAS_STABIL = 0.02  # perubahan di bawah 2% dianggap stabil


def tentukan_tren(harga: int | None, prediksi_besok: int | None) -> str | None:
    if harga is None or prediksi_besok is None:
        return None
    selisih = (prediksi_besok - harga) / harga
    if selisih > BATAS_STABIL:
        return "naik"
    if selisih < -BATAS_STABIL:
        return "turun"
    return "stabil"


@router.get(
    "/{kode}/ringkasan",
    response_model=RingkasanWilayah,
    responses={404: {"model": ErrorResponse, "description": "`WILAYAH_TIDAK_DITEMUKAN`"}},
)
def ringkasan_wilayah(kode: str, session: SessionDep):
    """Isi pop-up card peta: harga terbaru + prediksi besok + tren, untuk semua komoditas di satu wilayah."""
    wilayah = session.exec(select(Wilayah).where(Wilayah.kode == kode)).first()
    if wilayah is None:
        raise AppError(404, "WILAYAH_TIDAK_DITEMUKAN", "Wilayah tidak ditemukan")

    # harga terbaru per komoditas + jenis pasar: cari tanggal maksimum dulu, lalu ambil barisnya
    tanggal_terbaru = (
        select(
            HargaHarian.komoditas_id,
            HargaHarian.jenis_pasar,
            func.max(HargaHarian.tanggal).label("tanggal"),
        )
        .where(HargaHarian.wilayah_id == wilayah.id)
        .group_by(HargaHarian.komoditas_id, HargaHarian.jenis_pasar)
        .subquery()
    )
    harga = {
        (h.komoditas_id, h.jenis_pasar): h
        for h in session.exec(
            select(HargaHarian).join(
                tanggal_terbaru,
                and_(
                    HargaHarian.komoditas_id == tanggal_terbaru.c.komoditas_id,
                    HargaHarian.jenis_pasar == tanggal_terbaru.c.jenis_pasar,
                    HargaHarian.tanggal == tanggal_terbaru.c.tanggal,
                ),
            ).where(HargaHarian.wilayah_id == wilayah.id)
        ).all()
    }

    besok = prediksi.hari_ini() + timedelta(days=1)
    prediksi_besok = {
        (p.komoditas_id, p.jenis_pasar): p.harga
        for p in session.exec(
            select(PrediksiHarga).where(
                PrediksiHarga.wilayah_id == wilayah.id, PrediksiHarga.tanggal_prediksi == besok
            )
        ).all()
    }

    def ringkas_pasar(komoditas_id: int, jenis_pasar: str) -> RingkasanPasar:
        h = harga.get((komoditas_id, jenis_pasar))
        p = prediksi_besok.get((komoditas_id, jenis_pasar))
        return RingkasanPasar(
            harga=h.harga if h else None,
            tanggal=h.tanggal if h else None,
            sumber=h.sumber if h else None,
            prediksi_besok=p,
            tren=tentukan_tren(h.harga if h else None, p),
        )

    semua_komoditas = session.exec(select(Komoditas).order_by(Komoditas.nama)).all()
    return RingkasanWilayah(
        wilayah=WilayahRingkas.model_validate(wilayah),
        provinsi=wilayah.provinsi,
        tanggal_prediksi=besok,
        komoditas=[
            RingkasanKomoditas(
                komoditas=KomoditasRingkas.model_validate(k),
                tradisional=ringkas_pasar(k.id, "tradisional"),
                modern=ringkas_pasar(k.id, "modern"),
            )
            for k in semua_komoditas
        ],
    )
