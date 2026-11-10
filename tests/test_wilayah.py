import pytest

from app.models import Wilayah
from app.routers.wilayah import hitung_jarak_km

BLOK_M = {"lat": -6.2443, "lng": 106.8000}  # Kebayoran Baru, Jakarta Selatan


@pytest.fixture
def data_contoh(session):
    session.add_all(
        [
            Wilayah(kode="31.74", nama="Kota Jakarta Selatan", provinsi="DKI Jakarta", lat=-6.2615, lng=106.8106),
            Wilayah(kode="31.71", nama="Kota Jakarta Pusat", provinsi="DKI Jakarta", lat=-6.1805, lng=106.8284),
            Wilayah(kode="36.71", nama="Kota Tangerang", provinsi="Banten", lat=-6.1781, lng=106.6300),
        ]
    )
    session.commit()


def test_jarak_titik_yang_sama_nol():
    assert hitung_jarak_km(-6.2, 106.8, -6.2, 106.8) == 0


def test_jarak_satu_derajat_lintang():
    # 1 derajat lintang ≈ 111,19 km
    assert hitung_jarak_km(0, 0, 1, 0) == pytest.approx(111.19, abs=0.01)


def test_daftar_kosong(client):
    response = client.get("/wilayah")
    assert response.status_code == 200
    assert response.json() == []


def test_daftar_urut_provinsi_lalu_nama(client, data_contoh):
    response = client.get("/wilayah")
    assert [w["nama"] for w in response.json()] == [
        "Kota Tangerang",
        "Kota Jakarta Pusat",
        "Kota Jakarta Selatan",
    ]


def test_cari_nama_tidak_peka_huruf_besar_kecil(client, data_contoh):
    response = client.get("/wilayah", params={"q": "SELATAN"})
    assert [w["kode"] for w in response.json()] == ["31.74"]


def test_cari_lewat_provinsi(client, data_contoh):
    response = client.get("/wilayah", params={"q": "dki"})
    assert [w["kode"] for w in response.json()] == ["31.71", "31.74"]


def test_terdekat(client, data_contoh):
    response = client.get("/wilayah/terdekat", params=BLOK_M)
    assert response.status_code == 200
    data = response.json()
    assert data["kode"] == "31.74"
    assert data["nama"] == "Kota Jakarta Selatan"
    assert 0 < data["jarak_km"] < 5


def test_terdekat_koordinat_tidak_valid(client, data_contoh):
    response = client.get("/wilayah/terdekat", params={"lat": 100, "lng": 106.8})
    assert response.status_code == 422
    assert response.json() == {
        "kode": "INPUT_TIDAK_VALID",
        "pesan": "Input tidak valid",
        "detail": [{"field": "lat", "pesan": "harus ≤ 90"}],
    }


def test_terdekat_tanpa_koordinat(client, data_contoh):
    response = client.get("/wilayah/terdekat")
    assert response.status_code == 422
    assert response.json()["detail"] == [
        {"field": "lat", "pesan": "wajib diisi"},
        {"field": "lng", "pesan": "wajib diisi"},
    ]


def test_terdekat_belum_ada_data(client):
    response = client.get("/wilayah/terdekat", params=BLOK_M)
    assert response.status_code == 404
    assert response.json()["kode"] == "WILAYAH_TIDAK_DITEMUKAN"
