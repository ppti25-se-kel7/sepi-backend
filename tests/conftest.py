import os

# Tes tidak boleh menyentuh database Neon: paksa aplikasi memakai SQLite di memori.
# Harus diatur SEBELUM app di-import, karena engine dibuat saat import.
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402
from sqlmodel.pool import StaticPool  # noqa: E402

from app.database import get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def session():
    """Database SQLite baru yang kosong untuk setiap tes."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def login(monkeypatch):
    """Login palsu untuk tes endpoint yang wajib login: login("uid-budi") → header Authorization."""
    from datetime import datetime, timedelta, timezone

    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app import auth
    from app.config import settings

    kunci = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "firebase_project_id", "sepi-test")
    monkeypatch.setattr(auth, "ambil_kunci_publik", lambda token: kunci.public_key())

    def header(uid="uid-budi"):
        sekarang = datetime.now(timezone.utc)
        isi = {
            "iss": "https://securetoken.google.com/sepi-test",
            "aud": "sepi-test",
            "sub": uid,
            "iat": sekarang,
            "exp": sekarang + timedelta(hours=1),
        }
        return {"Authorization": f"Bearer {jwt.encode(isi, kunci, algorithm='RS256')}"}

    return header


@pytest.fixture
def client(session):
    """Client HTTP palsu yang memakai database tes, bukan database asli."""
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()
