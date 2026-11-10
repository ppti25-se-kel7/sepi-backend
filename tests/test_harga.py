from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import HargaHarian, Komoditas, Wilayah


@pytest.fixture
def data_contoh(session):
    beras = Komoditas(label="beras", nama="Beras", satuan="kg")
    jakbar = Wilayah(kode="31.73", nama="Kota Jakarta Barat", provinsi="DKI Jakarta", lat=-6.17, lng=106.76)
    depok = Wilayah(kode="32.76", nama="Kota Depok", provinsi="Jawa Barat", lat=-6.40, lng=106.79)
    session.add_all([beras, jakbar, depok])
    session.commit()

    def harga(wilayah, jenis_pasar, tanggal, nilai):
        return HargaHarian(
            tanggal=tanggal,
            komoditas_id=beras.id,
            wilayah_id=wilayah.id,
            jenis_pasar=jenis_pasar,
            harga=nilai,
            sumber="dummy",
        )

    session.add_all(
        [
            harga(jakbar, "tradisional", date(2026, 11, 1), 14000),
            harga(jakbar, "tradisional", date(2026, 11, 2), 15000),  # terbaru
            harga(jakbar, "modern", date(2026, 11, 2), 16500),
            harga(depok, "tradisional", date(2026, 11, 2), 99000),  # wilayah lain, tidak boleh tercampur
        ]
    )
    session.commit()
    return {"beras": beras, "jakbar": jakbar, "depok": depok}


def test_kedua_pasar_tersedia(client, data_contoh):
    response = client.get("/prices", params={"komoditas": "beras", "wilayah": "31.73"})
    assert response.status_code == 200
    data = response.json()
    assert data["komoditas"] == {"label": "beras", "nama": "Beras", "satuan": "kg"}
    assert data["wilayah"] == {"kode": "31.73", "nama": "Kota Jakarta Barat"}
    assert data["keterangan"] == "rata-rata wilayah"
    assert data["modern"] == {"status": "tersedia", "harga": 16500, "tanggal": "2026-11-02", "sumber": "dummy"}


def test_ambil_harga_terbaru(client, data_contoh):
    response = client.get("/prices", params={"komoditas": "beras", "wilayah": "31.73"})
    assert response.json()["tradisional"]["harga"] == 15000
    assert response.json()["tradisional"]["tanggal"] == "2026-11-02"


def test_pasar_belum_tersedia_null_bukan_nol(client, data_contoh):
    response = client.get("/prices", params={"komoditas": "beras", "wilayah": "32.76"})
    data = response.json()
    assert data["tradisional"]["harga"] == 99000
    assert data["modern"] == {"status": "belum_tersedia", "harga": None, "tanggal": None, "sumber": None}


def test_komoditas_tidak_ditemukan(client, data_contoh):
    response = client.get("/prices", params={"komoditas": "durian", "wilayah": "31.73"})
    assert response.status_code == 404
    assert response.json() == {"kode": "KOMODITAS_TIDAK_DITEMUKAN", "pesan": "Komoditas tidak ditemukan"}


def test_wilayah_tidak_ditemukan(client, data_contoh):
    response = client.get("/prices", params={"komoditas": "beras", "wilayah": "99.99"})
    assert response.status_code == 404
    assert response.json() == {"kode": "WILAYAH_TIDAK_DITEMUKAN", "pesan": "Wilayah tidak ditemukan"}


def test_parameter_kurang(client, data_contoh):
    response = client.get("/prices", params={"komoditas": "beras"})
    assert response.status_code == 422
    assert response.json()["kode"] == "INPUT_TIDAK_VALID"
    assert response.json()["detail"] == [{"field": "wilayah", "pesan": "wajib diisi"}]


def test_harga_dobel_ditolak(session, data_contoh):
    session.add(
        HargaHarian(
            tanggal=date(2026, 11, 2),
            komoditas_id=data_contoh["beras"].id,
            wilayah_id=data_contoh["jakbar"].id,
            jenis_pasar="modern",
            harga=17000,
            sumber="dummy",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_jenis_pasar_selain_tradisional_modern_ditolak(session, data_contoh):
    session.add(
        HargaHarian(
            tanggal=date(2026, 11, 3),
            komoditas_id=data_contoh["beras"].id,
            wilayah_id=data_contoh["jakbar"].id,
            jenis_pasar="grosir",
            harga=12000,
            sumber="dummy",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
