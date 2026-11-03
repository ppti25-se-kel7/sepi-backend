from math import asin, cos, radians, sin, sqrt
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, or_, select

from app.database import SessionDep
from app.models import Wilayah, WilayahPublic, WilayahTerdekat

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
    """Daftar wilayah, diurutkan berdasarkan provinsi lalu nama. Isi `q` untuk mencari di nama atau provinsi."""
    query = select(Wilayah).order_by(Wilayah.provinsi, Wilayah.nama)
    if q:
        pola = f"%{q.strip()}%"
        query = query.where(or_(col(Wilayah.nama).ilike(pola), col(Wilayah.provinsi).ilike(pola)))
    return session.exec(query).all()


@router.get("/terdekat", response_model=WilayahTerdekat)
def wilayah_terdekat(
    session: SessionDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
):
    """Wilayah yang titik tengahnya paling dekat dengan koordinat user (dari GPS HP)."""
    semua_wilayah = session.exec(select(Wilayah)).all()
    if not semua_wilayah:
        raise HTTPException(status_code=404, detail="Belum ada data wilayah")
    terdekat = min(semua_wilayah, key=lambda w: hitung_jarak_km(lat, lng, w.lat, w.lng))
    jarak = hitung_jarak_km(lat, lng, terdekat.lat, terdekat.lng)
    return WilayahTerdekat(**terdekat.model_dump(), jarak_km=round(jarak, 2))
