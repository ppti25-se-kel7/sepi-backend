from fastapi import APIRouter
from sqlmodel import col, or_, select

from app.database import SessionDep
from app.errors import AppError, ErrorResponse
from app.models import Komoditas, KomoditasPublic

router = APIRouter(prefix="/komoditas", tags=["komoditas"])


@router.get("", response_model=list[KomoditasPublic])
def daftar_komoditas(session: SessionDep, q: str | None = None):
    """Daftar komoditas, diurutkan berdasarkan nama. Isi `q` untuk mencari di nama, label, atau alias."""
    query = select(Komoditas).order_by(Komoditas.nama)
    if q:
        pola = f"%{q.strip()}%"
        query = query.where(
            or_(
                col(Komoditas.nama).ilike(pola),
                col(Komoditas.label).ilike(pola),
                col(Komoditas.alias).ilike(pola),
            )
        )
    return session.exec(query).all()


@router.get(
    "/{label}",
    response_model=KomoditasPublic,
    responses={404: {"model": ErrorResponse, "description": "`KOMODITAS_TIDAK_DITEMUKAN`"}},
)
def detail_komoditas(label: str, session: SessionDep):
    """Detail satu komoditas berdasarkan label, mis. `bawang_merah`."""
    komoditas = session.exec(select(Komoditas).where(Komoditas.label == label)).first()
    if komoditas is None:
        raise AppError(404, "KOMODITAS_TIDAK_DITEMUKAN", "Komoditas tidak ditemukan")
    return komoditas
