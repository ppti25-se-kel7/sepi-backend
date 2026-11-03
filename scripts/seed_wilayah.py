"""Isi tabel wilayah dengan data Jabodetabek.

Dummy data: daftar final menyesuaikan wilayah yang tersedia di sumber data harga (PIHPS/Bapanas).
Koordinat = perkiraan titik pusat kota/kabupaten. Kode = kode wilayah Kemendagri.
Aman dijalankan berulang kali: wilayah yang kodenya sudah ada akan diperbarui, bukan dibuat dobel.

Cara menjalankan (dari folder sempol-backend):
    python -m scripts.seed_wilayah
"""

from sqlmodel import Session, select

from app.database import engine
from app.models import Wilayah

DATA_WILAYAH = [
    # (kode, nama, provinsi, lat, lng)
    ("31.01", "Kabupaten Kepulauan Seribu", "DKI Jakarta", -5.7453, 106.6136),
    ("31.71", "Kota Jakarta Selatan", "DKI Jakarta", -6.2615, 106.8106),
    ("31.72", "Kota Jakarta Timur", "DKI Jakarta", -6.2250, 106.9004),
    ("31.73", "Kota Jakarta Pusat", "DKI Jakarta", -6.1805, 106.8284),
    ("31.74", "Kota Jakarta Barat", "DKI Jakarta", -6.1674, 106.7637),
    ("31.75", "Kota Jakarta Utara", "DKI Jakarta", -6.1384, 106.8634),
    ("32.01", "Kabupaten Bogor", "Jawa Barat", -6.4818, 106.8540),
    ("32.16", "Kabupaten Bekasi", "Jawa Barat", -6.3627, 107.1726),
    ("32.71", "Kota Bogor", "Jawa Barat", -6.5971, 106.8060),
    ("32.75", "Kota Bekasi", "Jawa Barat", -6.2383, 106.9756),
    ("32.76", "Kota Depok", "Jawa Barat", -6.4025, 106.7942),
    ("36.03", "Kabupaten Tangerang", "Banten", -6.2647, 106.4780),
    ("36.71", "Kota Tangerang", "Banten", -6.1781, 106.6300),
    ("36.74", "Kota Tangerang Selatan", "Banten", -6.2886, 106.7179),
]


def main():
    with Session(engine) as session:
        for kode, nama, provinsi, lat, lng in DATA_WILAYAH:
            wilayah = session.exec(select(Wilayah).where(Wilayah.kode == kode)).first()
            if wilayah is None:
                wilayah = Wilayah(kode=kode)
                print(f"tambah   {kode} {nama}")
            else:
                print(f"perbarui {kode} {nama}")
            wilayah.nama = nama
            wilayah.provinsi = provinsi
            wilayah.lat = lat
            wilayah.lng = lng
            session.add(wilayah)
        session.commit()


if __name__ == "__main__":
    main()
