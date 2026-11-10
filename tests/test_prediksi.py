from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.models import Komoditas, PrediksiHarga, Wilayah
from app.routers import prediksi
from scripts.impor_prediksi import PrediksiTidakValid, impor_prediksi

HARI_INI = date(2026, 11, 10)


@pytest.fixture(autouse=True)
def tanggal_tetap(monkeypatch):
    # tes tidak boleh bergantung pada tanggal saat tes dijalankan
    monkeypatch.setattr(prediksi, "hari_ini", lambda: HARI_INI)


@pytest.fixture
def data_contoh(session):
    session.add_all(
        [
            Komoditas(label="beras", nama="Beras", satuan="kg"),
            Wilayah(kode="32.01", nama="Kabupaten Bogor", provinsi="Jawa Barat", lat=-6.48, lng=106.85),
            Wilayah(kode="32.71", nama="Kota Bogor", provinsi="Jawa Barat", lat=-6.60, lng=106.81),
        ]
    )
    session.commit()


def baris(tanggal="2026-11-10", harga="15000", jenis_pasar="tradisional", wilayah="32.01", **ubah):
    return {
        "komoditas": "beras",
        "wilayah": wilayah,
        "jenis_pasar": jenis_pasar,
        "tanggal_prediksi": tanggal,
        "harga": harga,
        "harga_min": "",
        "harga_max": "",
        "versi_model": "v1",
        **ubah,
    }


def test_forecast_urut_dan_hanya_ke_depan(client, session, data_contoh):
    impor_prediksi(
        session,
        [
            baris("2026-11-12", "15400"),
            baris("2026-11-09", "14000"),  # kemarin: tidak ditampilkan
            baris("2026-11-10", "15000", harga_min="14500", harga_max="15500"),
            baris("2026-11-17", "16000"),  # hari ke-8: di luar 7 hari
            baris("2026-11-11", "15200", wilayah="32.71"),  # wilayah lain: tidak tercampur
        ],
    )
    response = client.get("/forecast", params={"komoditas": "beras", "wilayah": "32.01"})
    assert response.status_code == 200
    data = response.json()
    assert data["keterangan"] == "prediksi rata-rata wilayah"
    assert data["tradisional"]["status"] == "tersedia"
    assert data["tradisional"]["prediksi"] == [
        {"tanggal": "2026-11-10", "harga": 15000, "harga_min": 14500, "harga_max": 15500, "versi_model": "v1"},
        {"tanggal": "2026-11-12", "harga": 15400, "harga_min": None, "harga_max": None, "versi_model": "v1"},
    ]
    assert data["modern"] == {"status": "belum_tersedia", "prediksi": []}


def test_forecast_jumlah_hari(client, session, data_contoh):
    impor_prediksi(session, [baris("2026-11-10"), baris("2026-11-11"), baris("2026-11-12")])
    response = client.get("/forecast", params={"komoditas": "beras", "wilayah": "32.01", "hari": 2})
    assert [p["tanggal"] for p in response.json()["tradisional"]["prediksi"]] == ["2026-11-10", "2026-11-11"]


def test_forecast_hari_tidak_valid(client, data_contoh):
    response = client.get("/forecast", params={"komoditas": "beras", "wilayah": "32.01", "hari": 0})
    assert response.status_code == 422
    assert response.json()["detail"] == [{"field": "hari", "pesan": "harus ≥ 1"}]


def test_forecast_komoditas_dan_wilayah_tidak_ada(client, data_contoh):
    assert client.get("/forecast", params={"komoditas": "durian", "wilayah": "32.01"}).json()["kode"] == (
        "KOMODITAS_TIDAK_DITEMUKAN"
    )
    assert client.get("/forecast", params={"komoditas": "beras", "wilayah": "99.99"}).json()["kode"] == (
        "WILAYAH_TIDAK_DITEMUKAN"
    )


def test_impor_ulang_menimpa_tidak_dobel(session, data_contoh):
    assert impor_prediksi(session, [baris(harga="15000")]) == (1, 0)
    assert impor_prediksi(session, [baris(harga="15800", versi_model="v2")]) == (0, 1)
    semua = session.exec(select(PrediksiHarga)).all()
    assert [(p.harga, p.versi_model) for p in semua] == [(15800, "v2")]


def test_impor_salah_tidak_menyimpan_apa_pun(session, data_contoh):
    with pytest.raises(PrediksiTidakValid) as info:
        impor_prediksi(
            session,
            [
                baris("2026-11-10"),  # baris ini benar, tapi tetap tidak boleh tersimpan
                baris("2026-11-11", komoditas="durian"),
                baris("11/12/2026"),
                baris("2026-11-13", harga="15rb"),
                baris("2026-11-14", harga_min="16000"),
                baris("2026-11-15", jenis_pasar="grosir"),
                baris("2026-11-10"),
            ],
        )
    assert info.value.kesalahan == [
        "baris 3: komoditas 'durian' tidak ada di tabel komoditas",
        "baris 4: tanggal_prediksi harus format YYYY-MM-DD, bukan '11/12/2026'",
        "baris 5: harga harus bilangan bulat, bukan '15rb'",
        "baris 6: harga_min tidak boleh lebih besar dari harga",
        "baris 7: jenis_pasar harus tradisional/modern, bukan 'grosir'",
        "baris 8: dobel (komoditas, wilayah, jenis pasar, dan tanggal sama dengan baris lain)",
    ]
    assert session.exec(select(PrediksiHarga)).all() == []


def test_database_menolak_rentang_terbalik(session, data_contoh):
    session.add(
        PrediksiHarga(
            komoditas_id=1,
            wilayah_id=1,
            jenis_pasar="tradisional",
            tanggal_prediksi=HARI_INI,
            harga=15000,
            harga_max=14000,
            versi_model="v1",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
