import pytest

from app.models import Komoditas


@pytest.fixture
def data_contoh(session):
    session.add_all(
        [
            Komoditas(label="cabai_merah", nama="Cabai Merah", satuan="kg", alias="cabe"),
            Komoditas(label="bawang_merah", nama="Bawang Merah", satuan="kg"),
            Komoditas(label="beras", nama="Beras", satuan="kg"),
        ]
    )
    session.commit()


def test_daftar_kosong(client):
    response = client.get("/komoditas")
    assert response.status_code == 200
    assert response.json() == []


def test_daftar_urut_berdasarkan_nama(client, data_contoh):
    response = client.get("/komoditas")
    assert [k["nama"] for k in response.json()] == ["Bawang Merah", "Beras", "Cabai Merah"]


def test_cari_nama_tidak_peka_huruf_besar_kecil(client, data_contoh):
    response = client.get("/komoditas", params={"q": "BAWANG"})
    assert [k["label"] for k in response.json()] == ["bawang_merah"]


def test_cari_lewat_alias(client, data_contoh):
    response = client.get("/komoditas", params={"q": "cabe"})
    assert [k["label"] for k in response.json()] == ["cabai_merah"]


def test_cari_tidak_ketemu(client, data_contoh):
    response = client.get("/komoditas", params={"q": "durian"})
    assert response.json() == []


def test_detail_komoditas(client, data_contoh):
    response = client.get("/komoditas/beras")
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "beras"
    assert data["nama"] == "Beras"
    assert data["satuan"] == "kg"


def test_detail_komoditas_tidak_ada(client, data_contoh):
    response = client.get("/komoditas/durian")
    assert response.status_code == 404
    assert response.json() == {"kode": "KOMODITAS_TIDAK_DITEMUKAN", "pesan": "Komoditas tidak ditemukan"}
