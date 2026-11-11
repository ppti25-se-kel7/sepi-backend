from math import cos, radians
from typing import Annotated

from fastapi import APIRouter, Query
from sqlmodel import col, select

from app.database import SessionDep
from app.errors import ErrorResponse
from app.models import Pasar, PasarTerdekat, PerbandinganPasar
from app.routers.wilayah import hitung_jarak_km

router = APIRouter(prefix="/markets", tags=["pasar"])

KM_PER_DERAJAT = 111.32  # panjang 1 derajat lintang


@router.get(
    "/nearest",
    response_model=PerbandinganPasar,
    responses={422: {"model": ErrorResponse, "description": "`INPUT_TIDAK_VALID`: lat/lng/radius tidak valid"}},
)
def pasar_terdekat(
    session: SessionDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(gt=0, le=50, description="Batas pencarian")] = 10,
):
    """Pasar tradisional & pasar modern terdekat dari lokasi user, beserta jaraknya, dan mana yang lebih dekat."""
    # saring kasar dulu di database pakai kotak (lat/lng ± radius), baru hitung jarak tepat di Python
    selisih_lat = radius_km / KM_PER_DERAJAT
    selisih_lng = radius_km / (KM_PER_DERAJAT * max(cos(radians(lat)), 0.01))
    kandidat = session.exec(
        select(Pasar).where(
            col(Pasar.lat).between(lat - selisih_lat, lat + selisih_lat),
            col(Pasar.lng).between(lng - selisih_lng, lng + selisih_lng),
        )
    ).all()

    terdekat: dict[str, PasarTerdekat] = {}
    for pasar in kandidat:
        jarak = hitung_jarak_km(lat, lng, pasar.lat, pasar.lng)
        if jarak > radius_km:
            continue  # di dalam kotak tapi di luar lingkaran radius
        if pasar.jenis not in terdekat or jarak < terdekat[pasar.jenis].jarak_km:
            terdekat[pasar.jenis] = PasarTerdekat(**pasar.model_dump(), jarak_km=round(jarak, 2))

    lebih_dekat = min(terdekat, key=lambda jenis: terdekat[jenis].jarak_km) if terdekat else None
    return PerbandinganPasar(
        tradisional=terdekat.get("tradisional"),
        modern=terdekat.get("modern"),
        lebih_dekat=lebih_dekat,
        radius_km=radius_km,
    )
