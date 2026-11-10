from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlmodel import select

from app import auth
from app.config import settings
from app.models import Pengguna

PROJECT_ID = "sepi-test"

# Pengganti kunci Google: pasangan kunci RSA buatan sendiri, jadi tes tidak butuh internet/akun Firebase.
KUNCI_PRIBADI = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KUNCI_LAIN = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def firebase_palsu(monkeypatch):
    monkeypatch.setattr(settings, "firebase_project_id", PROJECT_ID)
    monkeypatch.setattr(auth, "ambil_kunci_publik", lambda token: KUNCI_PRIBADI.public_key())


def buat_token(kunci=KUNCI_PRIBADI, project_id=PROJECT_ID, berlaku=timedelta(hours=1), **isi_tambahan):
    """Buat token mirip ID token Firebase."""
    sekarang = datetime.now(timezone.utc)
    isi = {
        "iss": f"https://securetoken.google.com/{project_id}",
        "aud": project_id,
        "sub": "uid-budi",
        "iat": sekarang - timedelta(minutes=1),
        "exp": sekarang + berlaku,
        "email": "budi@gmail.com",
        "name": "Budi",
        **isi_tambahan,
    }
    return jwt.encode(isi, kunci, algorithm="RS256")


def header(token):
    return {"Authorization": f"Bearer {token}"}


def test_tanpa_token(client):
    response = client.get("/pengguna/saya")
    assert response.status_code == 401
    assert response.json() == {"kode": "BELUM_LOGIN", "pesan": "Silakan login terlebih dahulu"}


def test_login_pertama_kali_membuat_pengguna(client, session):
    response = client.get("/pengguna/saya", headers=header(buat_token()))
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "budi@gmail.com"
    assert data["nama"] == "Budi"
    assert "firebase_uid" not in data
    assert session.exec(select(Pengguna)).one().firebase_uid == "uid-budi"


def test_login_ulang_tidak_dobel_dan_nama_diperbarui(client, session):
    client.get("/pengguna/saya", headers=header(buat_token()))
    response = client.get("/pengguna/saya", headers=header(buat_token(name="Budi Santoso")))
    assert response.json()["nama"] == "Budi Santoso"
    assert len(session.exec(select(Pengguna)).all()) == 1


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(buat_token(berlaku=timedelta(minutes=-5)), id="kedaluwarsa"),
        pytest.param(buat_token(project_id="project-lain"), id="project-lain"),
        pytest.param(buat_token(kunci=KUNCI_LAIN), id="tanda-tangan-palsu"),
        pytest.param(buat_token(sub=""), id="tanpa-uid"),
        pytest.param("bukan-token", id="sembarang"),
    ],
)
def test_token_tidak_valid(client, session, token):
    response = client.get("/pengguna/saya", headers=header(token))
    assert response.status_code == 401
    assert response.json()["kode"] == "TOKEN_TIDAK_VALID"
    assert session.exec(select(Pengguna)).all() == []


def test_login_belum_diatur(client, monkeypatch):
    monkeypatch.setattr(settings, "firebase_project_id", "")
    response = client.get("/pengguna/saya", headers=header(buat_token()))
    assert response.status_code == 503
    assert response.json()["kode"] == "LOGIN_BELUM_DIATUR"
