"""Isi tabel resep & resep_bahan dengan resep rumahan sederhana.

Hanya bahan utama yang ada di daftar komoditas yang dicatat (jumlah dalam satuan komoditas: kg / liter),
bumbu lain dilihat di Cookpad lewat link pencarian. Daftar ini contoh awal, boleh ditambah.
Aman dijalankan berulang kali: resep yang namanya sudah ada diperbarui, bahannya diganti sesuai daftar.
Jalankan seed_komoditas lebih dulu.

Cara menjalankan (dari folder sempol-backend):
    python -m scripts.seed_resep
"""

from sqlmodel import Session, col, delete, select

from app.models import Komoditas, Resep, ResepBahan

DATA_RESEP = [
    # (nama, deskripsi, porsi, waktu_menit, {label komoditas: jumlah})
    ("Nasi Goreng Telur", "Nasi goreng rumahan dengan telur orak-arik.", 2, 20,
     {"beras": 0.25, "telur_ayam": 0.12, "bawang_merah": 0.03, "bawang_putih": 0.02, "cabai_merah": 0.02,
      "minyak_goreng": 0.03}),
    ("Telur Balado", "Telur rebus disiram sambal balado merah.", 4, 30,
     {"telur_ayam": 0.5, "cabai_merah": 0.15, "bawang_merah": 0.05, "bawang_putih": 0.02, "minyak_goreng": 0.1,
      "gula_pasir": 0.01}),
    ("Orek Telur", "Telur orak-arik pedas, cepat untuk lauk sehari-hari.", 2, 15,
     {"telur_ayam": 0.25, "bawang_merah": 0.03, "bawang_putih": 0.02, "cabai_merah": 0.03, "minyak_goreng": 0.03}),
    ("Bakwan Sayur", "Gorengan tepung berisi sayuran.", 4, 30,
     {"tepung_terigu": 0.25, "telur_ayam": 0.06, "bawang_putih": 0.02, "minyak_goreng": 0.25}),
    ("Pisang Goreng", "Pisang dibalut adonan tepung lalu digoreng.", 4, 20,
     {"tepung_terigu": 0.15, "gula_pasir": 0.03, "minyak_goreng": 0.3}),
    ("Sambal Bawang", "Sambal cabai dan bawang yang ditumis dengan minyak panas.", 4, 15,
     {"cabai_merah": 0.1, "bawang_merah": 0.05, "bawang_putih": 0.03, "minyak_goreng": 0.05, "gula_pasir": 0.005}),
    ("Bubur Nasi", "Bubur beras lembut dengan taburan bawang goreng.", 3, 60,
     {"beras": 0.15, "bawang_merah": 0.02, "minyak_goreng": 0.02}),
    ("Bolu Kukus", "Kue bolu sederhana yang dikukus.", 8, 45,
     {"tepung_terigu": 0.25, "gula_pasir": 0.2, "telur_ayam": 0.2, "minyak_goreng": 0.05}),
    ("Telur Dadar", "Telur dadar bawang, lauk paling praktis.", 1, 10,
     {"telur_ayam": 0.12, "bawang_merah": 0.02, "cabai_merah": 0.01, "minyak_goreng": 0.02}),
    ("Martabak Telur Mini", "Kulit tepung berisi telur dan bawang, digoreng.", 4, 30,
     {"tepung_terigu": 0.1, "telur_ayam": 0.25, "bawang_merah": 0.03, "minyak_goreng": 0.1}),
]


def sinkronkan_resep(session: Session, data: list[tuple]) -> tuple[int, int]:
    komoditas_id = {k.label: k.id for k in session.exec(select(Komoditas)).all()}
    kurang = sorted({label for *_, bahan in data for label in bahan} - set(komoditas_id))
    if kurang:
        raise ValueError(f"komoditas belum ada, jalankan seed_komoditas dulu: {', '.join(kurang)}")

    sudah_ada = {r.nama: r for r in session.exec(select(Resep)).all()}
    tambah = perbarui = 0
    for nama, deskripsi, porsi, waktu_menit, bahan in data:
        resep = sudah_ada.get(nama)
        if resep is None:
            resep = Resep(nama=nama, deskripsi=deskripsi, porsi=porsi)
            tambah += 1
        else:
            perbarui += 1
        resep.sqlmodel_update({"deskripsi": deskripsi, "porsi": porsi, "waktu_menit": waktu_menit})
        session.add(resep)
        session.flush()  # supaya resep baru langsung punya id
        # bahan resep diganti total sesuai daftar (hanya bahan resep ini)
        session.exec(delete(ResepBahan).where(col(ResepBahan.resep_id) == resep.id))
        session.add_all(
            ResepBahan(resep_id=resep.id, komoditas_id=komoditas_id[label], jumlah=jumlah)
            for label, jumlah in bahan.items()
        )
    session.commit()
    return tambah, perbarui


def main():
    from app.database import engine  # di sini, supaya tes bisa import fungsi di atas tanpa koneksi Neon

    with Session(engine) as session:
        tambah, perbarui = sinkronkan_resep(session, DATA_RESEP)
    print(f"tambah {tambah}, perbarui {perbarui} resep")


if __name__ == "__main__":
    main()
