"""Isi tabel prediksi_harga dengan prediksi PALSU untuk 7 hari ke depan (mulai hari ini, WIB).

Dummy data: dipakai sampai file prediksi asli dari model Kay tersedia. Semua baris diberi versi_model = "dummy".
Prediksi dibuat dari harga terbaru di harga_harian, digeser sedikit secara acak tapi tetap
(seed per komoditas, wilayah, jenis pasar, dan tanggal), dengan rentang ±5%.
Kombinasi yang belum punya harga (mis. pasar modern Kepulauan Seribu) tidak diberi prediksi.
Lewat jalur yang sama dengan impor CSV Kay (impor_prediksi), jadi aman dijalankan berulang kali.
Jalankan seed_harga_dummy lebih dulu.

Cara menjalankan (dari folder sempol-backend):
    python -m scripts.seed_prediksi_dummy
"""

import random
from datetime import timedelta

from sqlmodel import Session, select

from app.database import engine
from app.models import HargaHarian, Komoditas, Wilayah
from app.routers.prediksi import hari_ini
from scripts.impor_prediksi import impor_prediksi
from scripts.seed_harga_dummy import bulatkan_ratusan

JUMLAH_HARI = 7


def main():
    with Session(engine) as session:
        label = {k.id: k.label for k in session.exec(select(Komoditas)).all()}
        kode = {w.id: w.kode for w in session.exec(select(Wilayah)).all()}

        # harga terbaru untuk tiap komoditas + wilayah + jenis pasar
        harga_terbaru = {}
        for h in session.exec(select(HargaHarian).order_by(HargaHarian.tanggal)).all():
            harga_terbaru[(h.komoditas_id, h.wilayah_id, h.jenis_pasar)] = h.harga
        if not harga_terbaru:
            print("Tabel harga_harian kosong. Jalankan seed_harga_dummy dulu.")
            return

        mulai = hari_ini()
        daftar_baris = []
        for (komoditas_id, wilayah_id, jenis_pasar), harga in harga_terbaru.items():
            for i in range(JUMLAH_HARI):
                tanggal = mulai + timedelta(days=i)
                acak = random.Random(f"prediksi-{label[komoditas_id]}-{kode[wilayah_id]}-{jenis_pasar}-{tanggal}")
                perkiraan = harga * acak.uniform(0.97, 1.05)
                daftar_baris.append(
                    {
                        "komoditas": label[komoditas_id],
                        "wilayah": kode[wilayah_id],
                        "jenis_pasar": jenis_pasar,
                        "tanggal_prediksi": tanggal.isoformat(),
                        "harga": str(bulatkan_ratusan(perkiraan)),
                        "harga_min": str(bulatkan_ratusan(perkiraan * 0.95)),
                        "harga_max": str(bulatkan_ratusan(perkiraan * 1.05)),
                        "versi_model": "dummy",
                    }
                )

        tambah, perbarui = impor_prediksi(session, daftar_baris)
    print(f"tambah {tambah}, perbarui {perbarui} prediksi dummy ({mulai} s/d {mulai + timedelta(days=JUMLAH_HARI - 1)})")


if __name__ == "__main__":
    main()
