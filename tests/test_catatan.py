from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.models import CatatanItem, Komoditas, PrediksiHarga, Wilayah
from app.routers import prediksi
from app.routers.catatan import jumlah_dalam_satuan_komoditas

HARI_INI = date(2026, 11, 10)


@pytest.fixture(autouse=True)
def tanggal_tetap(monkeypatch):
    monkeypatch.setattr(prediksi, "hari_ini", lambda: HARI_INI)


@pytest.fixture
def data_contoh(session):
    beras = Komoditas(label="beras", nama="Beras", satuan="kg")
    minyak = Komoditas(label="minyak_goreng", nama="Minyak Goreng", satuan="liter")
    bawang = Komoditas(label="bawang_merah", nama="Bawang Merah", satuan="kg")
    bogor = Wilayah(kode="32.71", nama="Kota Bogor", provinsi="Jawa Barat", lat=-6.6, lng=106.8)
    session.add_all([beras, minyak, bawang, bogor])
    session.commit()

    def p(komoditas, tanggal, harga, jenis_pasar="tradisional", hmin=None, hmax=None):
        return PrediksiHarga(
            komoditas_id=komoditas.id, wilayah_id=bogor.id, jenis_pasar=jenis_pasar, tanggal_prediksi=tanggal,
            harga=harga, harga_min=hmin, harga_max=hmax, versi_model="v1",
        )

    session.add_all(
        [
            p(beras, date(2026, 11, 9), 10000),  # kemarin: tidak dipakai
            p(beras, date(2026, 11, 10), 16000, hmin=15000, hmax=17000),  # hari ini: dipakai
            p(beras, date(2026, 11, 11), 18000),
            p(beras, date(2026, 11, 10), 19000, jenis_pasar="modern"),
            p(minyak, date(2026, 11, 12), 20000),  # belum ada untuk hari ini → pakai tanggal terdekat
        ]
    )
    session.commit()


def buat_catatan(client, header, **isi):
    response = client.post("/catatan", json={"judul": "Belanja Senin", "wilayah": "32.71", **isi}, headers=header)
    assert response.status_code == 201, response.text
    return response.json()


def tambah(client, header, catatan_id, **isi):
    return client.post(f"/catatan/{catatan_id}/item", json=isi, headers=header)


@pytest.mark.parametrize(
    "jumlah, satuan, dasar, hasil",
    [(250, "gram", "kg", 0.25), (2, "ons", "kg", 0.2), (0.25, "Kg", "kg", 0.25), (500, "ml", "liter", 0.5),
     (1, "kresek", "kg", None), (1, "gram", "liter", None)],
)
def test_konversi_satuan(jumlah, satuan, dasar, hasil):
    assert jumlah_dalam_satuan_komoditas(jumlah, satuan, dasar) == (pytest.approx(hasil) if hasil else None)


def test_wajib_login(client):
    assert client.get("/catatan").json()["kode"] == "BELUM_LOGIN"


def test_harga_dari_prediksi_dikali_jumlah(client, login, data_contoh):
    header = login()
    catatan = buat_catatan(client, header)
    data = tambah(client, header, catatan["id"], komoditas="beras", jumlah=250, satuan="gram").json()
    item = data["item"][0]
    assert item["nama"] == "Beras"
    assert item["status_harga"] == "prediksi"
    assert (item["harga_perkiraan"], item["harga_min"], item["harga_max"]) == (4000, 3800, 4300)
    assert item["tanggal_prediksi"] == "2026-11-10"
    assert (data["total_perkiraan"], data["total_min"], data["total_max"]) == (4000, 3800, 4300)


def test_pakai_prediksi_terdekat_dan_jenis_pasar(client, login, data_contoh):
    header = login()
    catatan = buat_catatan(client, header, jenis_pasar="modern")
    data = tambah(client, header, catatan["id"], komoditas="beras", jumlah=1, satuan="kg").json()
    assert data["item"][0]["harga_perkiraan"] == 19000
    catatan = buat_catatan(client, header)
    data = tambah(client, header, catatan["id"], komoditas="minyak_goreng", jumlah=2, satuan="liter").json()
    assert data["item"][0]["harga_perkiraan"] == 40000
    assert data["item"][0]["tanggal_prediksi"] == "2026-11-12"


def test_status_harga_kalau_tidak_bisa_dihitung(client, login, data_contoh):
    header = login()
    catatan_id = buat_catatan(client, header)["id"]
    tambah(client, header, catatan_id, nama="Kerupuk", jumlah=1, satuan="bungkus")
    tambah(client, header, catatan_id, komoditas="beras", jumlah=1, satuan="kresek")
    data = tambah(client, header, catatan_id, komoditas="bawang_merah", jumlah=1, satuan="ons").json()
    assert [i["status_harga"] for i in data["item"]] == [
        "isi_manual", "satuan_tidak_bisa_dihitung", "prediksi_belum_tersedia",
    ]
    assert data["item_tanpa_harga"] == 3
    assert data["total_perkiraan"] == 0

    tanpa_wilayah = client.post("/catatan", json={"judul": "Tanpa wilayah"}, headers=header).json()
    data = tambah(client, header, tanpa_wilayah["id"], komoditas="beras", jumlah=1, satuan="kg").json()
    assert data["item"][0]["status_harga"] == "wilayah_belum_dipilih"


def test_harga_manual_menimpa_dan_bisa_dikembalikan(client, login, data_contoh):
    header = login()
    catatan_id = buat_catatan(client, header)["id"]
    data = tambah(client, header, catatan_id, komoditas="beras", jumlah=1, satuan="kg", harga_manual=15000).json()
    item = data["item"][0]
    assert (item["status_harga"], item["harga_perkiraan"]) == ("manual", 15000)

    data = client.patch(f"/catatan/{catatan_id}/item/{item['id']}", json={"harga_manual": None}, headers=header).json()
    assert (data["item"][0]["status_harga"], data["item"][0]["harga_perkiraan"]) == ("prediksi", 16000)


def test_centang_sudah_dibeli_dan_hapus_item(client, login, data_contoh):
    header = login()
    catatan_id = buat_catatan(client, header)["id"]
    tambah(client, header, catatan_id, nama="Kerupuk", jumlah=1, satuan="bungkus")
    item_id = tambah(client, header, catatan_id, komoditas="beras", jumlah=1, satuan="kg").json()["item"][1]["id"]

    data = client.patch(f"/catatan/{catatan_id}/item/{item_id}", json={"sudah_dibeli": True}, headers=header).json()
    assert data["jumlah_sudah_dibeli"] == 1
    daftar = client.get("/catatan", headers=header).json()
    assert (daftar[0]["jumlah_item"], daftar[0]["jumlah_sudah_dibeli"]) == (2, 1)

    data = client.delete(f"/catatan/{catatan_id}/item/{item_id}", headers=header).json()
    assert [i["nama"] for i in data["item"]] == ["Kerupuk"]


def test_ubah_dan_hapus_catatan(client, login, session, data_contoh):
    header = login()
    catatan_id = buat_catatan(client, header)["id"]
    tambah(client, header, catatan_id, nama="Kerupuk", jumlah=1, satuan="bungkus")

    data = client.patch(f"/catatan/{catatan_id}", json={"judul": "Belanja Selasa", "wilayah": None}, headers=header)
    assert (data.json()["judul"], data.json()["wilayah"]) == ("Belanja Selasa", None)

    assert client.delete(f"/catatan/{catatan_id}", headers=header).status_code == 204
    assert client.get(f"/catatan/{catatan_id}", headers=header).json()["kode"] == "CATATAN_TIDAK_DITEMUKAN"
    assert session.exec(select(CatatanItem)).all() == []


def test_catatan_orang_lain_tidak_bisa_dibuka(client, login, data_contoh):
    catatan_id = buat_catatan(client, login("uid-budi"))["id"]
    header_ani = login("uid-ani")
    assert client.get(f"/catatan/{catatan_id}", headers=header_ani).status_code == 404
    assert client.delete(f"/catatan/{catatan_id}", headers=header_ani).status_code == 404
    assert client.get("/catatan", headers=header_ani).json() == []


@pytest.mark.parametrize(
    "isi, field, pesan",
    [
        ({"jumlah": 1, "satuan": "kg"}, "body", "isi salah satu: komoditas (dari daftar) atau nama (ketik sendiri)"),
        ({"komoditas": "beras", "nama": "Beras", "jumlah": 1, "satuan": "kg"}, "body",
         "isi salah satu: komoditas (dari daftar) atau nama (ketik sendiri)"),
        ({"nama": "Kerupuk", "jumlah": 0, "satuan": "kg"}, "jumlah", "harus > 0"),
        ({"nama": "Kerupuk", "jumlah": 1, "satuan": ""}, "satuan", "wajib diisi"),
    ],
)
def test_input_item_tidak_valid(client, login, data_contoh, isi, field, pesan):
    header = login()
    catatan_id = buat_catatan(client, header)["id"]
    response = tambah(client, header, catatan_id, **isi)
    assert response.status_code == 422
    assert response.json()["detail"] == [{"field": field, "pesan": pesan}]


def test_komoditas_dan_wilayah_tidak_ada(client, login, data_contoh):
    header = login()
    assert client.post("/catatan", json={"judul": "x", "wilayah": "99.99"}, headers=header).json()["kode"] == (
        "WILAYAH_TIDAK_DITEMUKAN"
    )
    catatan_id = buat_catatan(client, header)["id"]
    response = tambah(client, header, catatan_id, komoditas="durian", jumlah=1, satuan="kg")
    assert response.json()["kode"] == "KOMODITAS_TIDAK_DITEMUKAN"


def test_database_menolak_item_tanpa_nama_dan_komoditas(session, data_contoh):
    session.add(CatatanItem(catatan_id=1, jumlah=1, satuan="kg"))
    with pytest.raises(IntegrityError):
        session.commit()
