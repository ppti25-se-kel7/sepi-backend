import time

import pytest

from app.config import settings
from app.dokumentasi import NAMA_COOKIE, tanda_tangan


@pytest.fixture
def login_aktif(monkeypatch):
    monkeypatch.setattr(settings, "docs_username", "tim")
    monkeypatch.setattr(settings, "docs_password", "rahasia-123")


def masuk(client, username="tim", password="rahasia-123"):
    return client.post(
        "/docs/login",
        content=f"username={username}&password={password}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def test_tanpa_password_dokumentasi_terbuka(client, monkeypatch):
    monkeypatch.setattr(settings, "docs_password", "")
    assert client.get("/docs").status_code == 200
    assert client.get("/swagger").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "SEPI API"
    assert "Keluar" not in client.get("/docs").text  # tidak ada tombol keluar kalau login tidak aktif


@pytest.mark.parametrize("alamat", ["/docs", "/swagger", "/redoc"])
def test_belum_login_diarahkan_ke_halaman_login(client, login_aktif, alamat):
    response = client.get(alamat, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/docs/login"


def test_openapi_json_belum_login(client, login_aktif):
    response = client.get("/openapi.json")
    assert response.status_code == 401
    assert response.json()["kode"] == "DOKUMENTASI_BELUM_LOGIN"


def test_halaman_login(client, login_aktif):
    response = client.get("/docs/login")
    assert response.status_code == 200
    assert "Dokumentasi API" in response.text
    assert 'name="password"' in response.text


def test_login_salah(client, login_aktif):
    response = masuk(client, password="salah")
    assert response.status_code == 401
    assert "Username atau password salah" in response.text
    assert NAMA_COOKIE not in response.cookies


def test_login_benar_lalu_bisa_buka_dan_keluar(client, login_aktif):
    response = masuk(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/docs"

    halaman = client.get("/docs")  # cookie tersimpan di client
    assert halaman.status_code == 200
    assert "/docs/logout" in halaman.text
    assert client.get("/openapi.json").status_code == 200

    client.get("/docs/logout")
    assert client.get("/docs", follow_redirects=False).status_code == 303


def test_cookie_palsu_atau_kedaluwarsa_ditolak(client, login_aktif):
    kedaluwarsa = int(time.time()) - 10
    for isi in ["123.palsu", f"{kedaluwarsa}.{tanda_tangan(kedaluwarsa)}", "ngawur"]:
        client.cookies.set(NAMA_COOKIE, isi)
        assert client.get("/docs", follow_redirects=False).status_code == 303


def test_ganti_password_membatalkan_login_lama(client, login_aktif, monkeypatch):
    masuk(client)
    monkeypatch.setattr(settings, "docs_password", "password-baru")
    assert client.get("/docs", follow_redirects=False).status_code == 303
