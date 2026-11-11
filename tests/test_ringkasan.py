from datetime import date

import pytest

from app.models import HargaHarian, Komoditas, PrediksiHarga, Wilayah
from app.routers import prediksi
from app.routers.wilayah import tentukan_tren


@pytest.fixture(autouse=True)
def tanggal_tetap(monkeypatch):
    monkeypatch.setattr(prediksi, "hari_ini", lambda: date(2026, 11, 10))


@pytest.fixture
def data_contoh(session):
    beras = Komoditas(label="beras", nama="Beras", satuan="kg")
    cabai = Komoditas(label="cabai_merah", nama="Cabai Merah", satuan="kg")
    bogor = Wilayah(kode="32.71", nama="Kota Bogor", provinsi="Jawa Barat", lat=-6.6, lng=106.8)
    depok = Wilayah(kode="32.76", nama="Kota Depok", provinsi="Jawa Barat", lat=-6.4, lng=106.8)
    session.add_all([beras, cabai, bogor, depok])
    session.commit()

    def h(wilayah, tanggal, jenis_pasar, nilai):
        return HargaHarian(tanggal=tanggal, komoditas_id=beras.id, wilayah_id=wilayah.id,
                           jenis_pasar=jenis_pasar, harga=nilai, sumber="PIHPS")

    def p(jenis_pasar, tanggal, nilai):
        return PrediksiHarga(komoditas_id=beras.id, wilayah_id=bogor.id, jenis_pasar=jenis_pasar,
                             tanggal_prediksi=tanggal, harga=nilai, versi_model="v1")

    session.add_all(
        [
            h(bogor, date(2026, 11, 9), "tradisional", 15000),
            h(bogor, date(2026, 11, 10), "tradisional", 16000),  # terbaru
            h(bogor, date(2026, 11, 10), "modern", 17000),
            h(depok, date(2026, 11, 10), "tradisional", 99000),  # wilayah lain
            p("tradisional", date(2026, 11, 11), 16800),  # besok: naik 5%
            p("tradisional", date(2026, 11, 12), 10000),  # lusa: tidak dipakai
            p("modern", date(2026, 11, 11), 17100),  # besok: stabil
        ]
    )
    session.commit()


@pytest.mark.parametrize(
    "harga, besok, tren",
    [(10000, 10300, "naik"), (10000, 9700, "turun"), (10000, 10150, "stabil"), (None, 10000, None), (10000, None, None)],
)
def test_tren(harga, besok, tren):
    assert tentukan_tren(harga, besok) == tren


def test_ringkasan_semua_komoditas(client, data_contoh):
    response = client.get("/wilayah/32.71/ringkasan")
    assert response.status_code == 200
    data = response.json()
    assert data["wilayah"] == {"kode": "32.71", "nama": "Kota Bogor"}
    assert data["provinsi"] == "Jawa Barat"
    assert data["tanggal_prediksi"] == "2026-11-11"
    assert [k["komoditas"]["label"] for k in data["komoditas"]] == ["beras", "cabai_merah"]

    beras = data["komoditas"][0]
    assert beras["tradisional"] == {
        "harga": 16000, "tanggal": "2026-11-10", "sumber": "PIHPS", "prediksi_besok": 16800, "tren": "naik",
    }
    assert (beras["modern"]["harga"], beras["modern"]["tren"]) == (17000, "stabil")

    cabai = data["komoditas"][1]  # belum ada data sama sekali: null, bukan 0
    assert cabai["tradisional"] == {"harga": None, "tanggal": None, "sumber": None, "prediksi_besok": None, "tren": None}


def test_ringkasan_wilayah_tidak_ada(client, data_contoh):
    response = client.get("/wilayah/99.99/ringkasan")
    assert response.status_code == 404
    assert response.json()["kode"] == "WILAYAH_TIDAK_DITEMUKAN"
