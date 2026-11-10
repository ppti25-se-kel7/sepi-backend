import re
from datetime import date

from sqlmodel import select

from app.models import HargaHarian, Komoditas, PrediksiHarga, Wilayah
from app.routers.wilayah import hitung_jarak_km
from scripts.seed_wilayah import DATA_WILAYAH, sinkronkan_wilayah

SENTUL_CITY = (-6.5640, 106.8590)


def test_daftar_86_kab_kota_unik_dan_valid():
    kode = [baris[0] for baris in DATA_WILAYAH]
    assert len(kode) == len(set(kode)) == 86
    for kode, nama, provinsi, lat, lng in DATA_WILAYAH:
        assert re.fullmatch(r"\d{2}\.\d{2}", kode), kode
        assert nama == nama.strip() and nama.startswith(("Kota ", "Kabupaten ")), nama
        assert -11 < lat < 6 and 95 < lng < 141, kode  # masih di dalam Indonesia


def test_kode_dki_sesuai_kemendagri():
    nama = {baris[0]: baris[1] for baris in DATA_WILAYAH}
    assert nama["31.71"] == "Kota Administrasi Jakarta Pusat"
    assert nama["31.74"] == "Kota Administrasi Jakarta Selatan"


def test_sentul_paling_dekat_ke_kota_bogor():
    terdekat = min(DATA_WILAYAH, key=lambda b: hitung_jarak_km(*SENTUL_CITY, b[3], b[4]))
    assert terdekat[1] == "Kota Bogor"


def wilayah_lama_dengan_harga(session, sumber):
    beras = Komoditas(label="beras", nama="Beras", satuan="kg")
    lama = Wilayah(kode="32.01", nama="Kabupaten Bogor", provinsi="Jawa Barat", lat=-6.48, lng=106.85)
    session.add_all([beras, lama])
    session.commit()
    session.add_all(
        [
            HargaHarian(
                tanggal=date(2026, 11, 1), komoditas_id=beras.id, wilayah_id=lama.id,
                jenis_pasar="tradisional", harga=15000, sumber=sumber,
            ),
            PrediksiHarga(
                komoditas_id=beras.id, wilayah_id=lama.id, jenis_pasar="tradisional",
                tanggal_prediksi=date(2026, 11, 12), harga=15200, versi_model="dummy",
            ),
        ]
    )
    session.commit()


def test_sinkron_tanpa_flag_tidak_menghapus(session):
    wilayah_lama_dengan_harga(session, "dummy")
    ringkasan = sinkronkan_wilayah(session, DATA_WILAYAH)
    assert ringkasan["tambah"] == 86
    assert ringkasan["di_luar_daftar"] == ["32.01 Kabupaten Bogor"]
    assert ringkasan["dihapus"] == []
    assert len(session.exec(select(Wilayah)).all()) == 87


def test_sinkron_ulang_memperbarui_tidak_dobel(session):
    sinkronkan_wilayah(session, DATA_WILAYAH)
    ringkasan = sinkronkan_wilayah(session, DATA_WILAYAH)
    assert (ringkasan["tambah"], ringkasan["perbarui"]) == (0, 86)
    assert len(session.exec(select(Wilayah)).all()) == 86


def test_hapus_wilayah_lama_beserta_data_dummy(session):
    wilayah_lama_dengan_harga(session, "dummy")
    ringkasan = sinkronkan_wilayah(session, DATA_WILAYAH, hapus_di_luar_daftar=True)
    assert ringkasan["dihapus"] == ["32.01 Kabupaten Bogor"]
    assert session.exec(select(Wilayah).where(Wilayah.kode == "32.01")).first() is None
    assert session.exec(select(HargaHarian)).all() == []
    assert session.exec(select(PrediksiHarga)).all() == []


def test_wilayah_dengan_data_asli_tidak_dihapus(session):
    wilayah_lama_dengan_harga(session, "PIHPS")
    ringkasan = sinkronkan_wilayah(session, DATA_WILAYAH, hapus_di_luar_daftar=True)
    assert ringkasan["dihapus"] == []
    assert ringkasan["tidak_dihapus"] == ["32.01 Kabupaten Bogor (1 data asli)"]
    assert session.exec(select(Wilayah).where(Wilayah.kode == "32.01")).first() is not None
