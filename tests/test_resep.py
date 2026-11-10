from datetime import date

import pytest
from sqlmodel import select

from app.models import Komoditas, ResepBahan
from app.routers import prediksi
from app.routers.resep import link_cookpad
from scripts.seed_resep import DATA_RESEP, sinkronkan_resep

LABEL = ["beras", "telur_ayam", "bawang_merah", "bawang_putih", "cabai_merah", "minyak_goreng", "gula_pasir",
         "tepung_terigu"]


@pytest.fixture
def komoditas(session):
    session.add_all(Komoditas(label=label, nama=label.replace("_", " ").title(), satuan="kg") for label in LABEL)
    session.commit()


def atur_tanggal(monkeypatch, tanggal):
    monkeypatch.setattr(prediksi, "hari_ini", lambda: tanggal)


def test_link_cookpad():
    assert link_cookpad("Nasi Goreng Telur") == "https://cookpad.com/id/cari/nasi%20goreng%20telur"


def test_belum_ada_resep(client):
    response = client.get("/recipes/today")
    assert response.status_code == 404
    assert response.json()["kode"] == "RESEP_TIDAK_DITEMUKAN"


def test_resep_hari_ini_bergiliran(client, session, komoditas, monkeypatch):
    sinkronkan_resep(session, DATA_RESEP)
    atur_tanggal(monkeypatch, date(2026, 11, 10))
    hari_ini = client.get("/recipes/today").json()
    assert client.get("/recipes/today").json()["nama"] == hari_ini["nama"]  # sama sepanjang hari

    atur_tanggal(monkeypatch, date(2026, 11, 11))
    besok = client.get("/recipes/today").json()
    assert besok["nama"] != hari_ini["nama"]
    assert besok["tanggal"] == "2026-11-11"
    assert besok["link_cookpad"].startswith("https://cookpad.com/id/cari/")


def test_isi_bahan(client, session, komoditas, monkeypatch):
    sinkronkan_resep(session, DATA_RESEP[:1])  # hanya Nasi Goreng Telur
    atur_tanggal(monkeypatch, date(2026, 11, 10))
    data = client.get("/recipes/today").json()
    assert (data["nama"], data["porsi"], data["waktu_menit"]) == ("Nasi Goreng Telur", 2, 20)
    assert data["bahan"][0] == {"komoditas": {"label": "beras", "nama": "Beras", "satuan": "kg"}, "jumlah": 0.25}
    assert len(data["bahan"]) == 6


def test_seed_resep_ulang_tidak_dobel(session, komoditas):
    assert sinkronkan_resep(session, DATA_RESEP) == (10, 0)
    assert sinkronkan_resep(session, DATA_RESEP) == (0, 10)
    jumlah_bahan = sum(len(bahan) for *_, bahan in DATA_RESEP)
    assert len(session.exec(select(ResepBahan)).all()) == jumlah_bahan


def test_seed_resep_tanpa_komoditas(session):
    with pytest.raises(ValueError, match="jalankan seed_komoditas dulu"):
        sinkronkan_resep(session, DATA_RESEP)
