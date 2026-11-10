"""Isi tabel harga_harian dengan harga PALSU untuk beberapa hari terakhir.

Dummy data: dipakai sampai data asli dari PIHPS/Bapanas tersedia. Semua baris diberi sumber = "dummy".
Harga dibuat acak tapi tetap (random dengan seed per komoditas, wilayah, dan tanggal),
jadi harga untuk tanggal yang sama selalu sama kapan pun script dijalankan.
Kota Tual sengaja tidak diberi harga pasar modern, untuk contoh status "belum_tersedia".
Aman dijalankan berulang kali: harga yang sudah ada akan diperbarui, bukan dibuat dobel.
Komoditas + wilayah yang sudah punya data asli (sumber selain "dummy", mis. PIHPS) dilewati.
Jalankan seed_komoditas dan seed_wilayah lebih dulu.

Cara menjalankan (dari folder sempol-backend):
    python -m scripts.seed_harga_dummy
"""

import random
from datetime import date, timedelta

from sqlmodel import Session, col, select

from app.database import engine
from app.models import HargaHarian, Komoditas, Wilayah

JUMLAH_HARI = 7

HARGA_DASAR = {
    # label: perkiraan harga pasar tradisional (rupiah per satuan)
    "beras": 15000,
    "telur_ayam": 30000,
    "bawang_merah": 40000,
    "bawang_putih": 42000,
    "cabai_merah": 55000,
    "minyak_goreng": 18000,
    "gula_pasir": 18000,
    "tepung_terigu": 13000,
}

WILAYAH_TANPA_PASAR_MODERN = {"81.72"}  # Kota Tual


def bulatkan_ratusan(nilai: float) -> int:
    return int(round(nilai / 100) * 100)


def main():
    hari_ini = date.today()
    daftar_tanggal = [hari_ini - timedelta(days=i) for i in range(JUMLAH_HARI)]

    with Session(engine) as session:
        semua_komoditas = session.exec(select(Komoditas).where(col(Komoditas.label).in_(HARGA_DASAR))).all()
        semua_wilayah = session.exec(select(Wilayah)).all()
        if not semua_komoditas or not semua_wilayah:
            print("Data komoditas/wilayah kosong. Jalankan seed_komoditas dan seed_wilayah dulu.")
            return

        # ambil semua harga dummy yang sudah ada sekaligus, supaya tidak query satu per satu ke Neon
        sudah_ada = {
            (h.komoditas_id, h.wilayah_id, h.jenis_pasar, h.tanggal): h
            for h in session.exec(select(HargaHarian).where(HargaHarian.sumber == "dummy")).all()
        }

        # komoditas + wilayah yang sudah punya data asli (mis. PIHPS) tidak diberi harga dummy sama sekali,
        # supaya data asli tidak bentrok/tercampur dengan data palsu
        punya_data_asli = set(
            session.exec(
                select(HargaHarian.komoditas_id, HargaHarian.wilayah_id).where(HargaHarian.sumber != "dummy").distinct()
            ).all()
        )

        jumlah_tambah = jumlah_perbarui = 0
        for komoditas in semua_komoditas:
            for wilayah in semua_wilayah:
                if (komoditas.id, wilayah.id) in punya_data_asli:
                    continue
                for tanggal in daftar_tanggal:
                    # seed per komoditas+wilayah+tanggal: harga tanggal yang sama selalu sama, kapan pun dijalankan
                    acak = random.Random(f"{komoditas.label}-{wilayah.kode}-{tanggal}")
                    # harga tradisional bervariasi ±10%, modern sekitar 5–20% lebih mahal
                    tradisional = HARGA_DASAR[komoditas.label] * acak.uniform(0.9, 1.1)
                    harga_per_pasar = {"tradisional": tradisional, "modern": tradisional * acak.uniform(1.05, 1.2)}
                    if wilayah.kode in WILAYAH_TANPA_PASAR_MODERN:
                        del harga_per_pasar["modern"]

                    for jenis_pasar, nilai in harga_per_pasar.items():
                        kunci = (komoditas.id, wilayah.id, jenis_pasar, tanggal)
                        harga = sudah_ada.get(kunci)
                        if harga is None:
                            harga = HargaHarian(
                                komoditas_id=komoditas.id,
                                wilayah_id=wilayah.id,
                                jenis_pasar=jenis_pasar,
                                tanggal=tanggal,
                                sumber="dummy",
                            )
                            jumlah_tambah += 1
                        else:
                            jumlah_perbarui += 1
                        harga.harga = bulatkan_ratusan(nilai)
                        session.add(harga)
        session.commit()

    print(f"tambah {jumlah_tambah}, perbarui {jumlah_perbarui} harga dummy ({daftar_tanggal[-1]} s/d {hari_ini})")
    print(f"dilewati {len(punya_data_asli)} pasangan komoditas+wilayah yang sudah punya data asli")


if __name__ == "__main__":
    main()
