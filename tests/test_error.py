from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app


def test_alamat_tidak_ada(client):
    response = client.get("/alamat-ngawur")
    assert response.status_code == 404
    assert response.json() == {"kode": "TIDAK_DITEMUKAN", "pesan": "Alamat tidak ditemukan"}


def test_metode_tidak_diizinkan(client):
    response = client.post("/komoditas")
    assert response.status_code == 405
    assert response.json()["kode"] == "METODE_TIDAK_DIIZINKAN"


def test_input_bukan_angka(client):
    response = client.get("/wilayah/terdekat", params={"lat": "abc", "lng": 106.8})
    assert response.status_code == 422
    assert response.json()["detail"] == [{"field": "lat", "pesan": "harus berupa angka"}]


def test_kesalahan_server_tidak_membocorkan_detail():
    def session_rusak():
        raise RuntimeError("password database bocor")

    app.dependency_overrides[get_session] = session_rusak
    try:
        # raise_server_exceptions=False: dapatkan respons 500 seperti yang diterima Flutter
        response = TestClient(app, raise_server_exceptions=False).get("/komoditas")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {"kode": "KESALAHAN_SERVER", "pesan": "Terjadi kesalahan di server, coba lagi nanti"}
    assert "bocor" not in response.text
