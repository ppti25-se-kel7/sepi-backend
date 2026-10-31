"""Isi tabel komoditas dengan data contoh.

DATA SEMENTARA: daftar final menunggu kesepakatan tim (label harus sama persis dengan label model CV).
Aman dijalankan berulang kali: komoditas yang labelnya sudah ada akan diperbarui, bukan dibuat dobel.

Cara menjalankan (dari folder sempol-backend):
    python -m scripts.seed_komoditas
"""

from sqlmodel import Session, select

from app.database import engine
from app.models import Komoditas

DATA_KOMODITAS = [
    # (label, nama, satuan, alias)
    ("beras", "Beras", "kg", None),
    ("telur_ayam", "Telur Ayam", "kg", "telor"),
    ("bawang_merah", "Bawang Merah", "kg", "brambang"),
    ("bawang_putih", "Bawang Putih", "kg", None),
    ("cabai_merah", "Cabai Merah", "kg", "cabe, cabe merah"),
    ("minyak_goreng", "Minyak Goreng", "liter", "minyak"),
    ("gula_pasir", "Gula Pasir", "kg", "gula"),
    ("tepung_terigu", "Tepung Terigu", "kg", "terigu, tepung"),
]


def main():
    with Session(engine) as session:
        for label, nama, satuan, alias in DATA_KOMODITAS:
            komoditas = session.exec(select(Komoditas).where(Komoditas.label == label)).first()
            if komoditas is None:
                komoditas = Komoditas(label=label)
                print(f"tambah   {label}")
            else:
                print(f"perbarui {label}")
            komoditas.nama = nama
            komoditas.satuan = satuan
            komoditas.alias = alias
            session.add(komoditas)
        session.commit()


if __name__ == "__main__":
    main()
