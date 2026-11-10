"""Isi tabel wilayah dengan kabupaten/kota yang dicakup PIHPS (Bank Indonesia).

PIHPS memakai 82 kota sampel IHK BPS. Di sini DKI Jakarta dipecah menjadi 5 kota administrasi,
jadi totalnya 86 kab/kota. Wilayah lain (mis. Kabupaten Bogor) tidak punya data harga resmi sendiri;
lewat /wilayah/terdekat user diarahkan ke kota sampel terdekat (Sentul → Kota Bogor).

Kode = kode wilayah Kemendagri (Kepmendagri No 300.2.2-2138 Tahun 2025).
Koordinat = titik pusat kota / ibukota kabupaten.
Sumber kode & koordinat: https://github.com/cahyadsn/wilayah (lisensi MIT, (c) Cahya DSN).

Aman dijalankan berulang kali: wilayah yang kodenya sudah ada akan diperbarui, bukan dibuat dobel.
Wilayah lama yang tidak ada di daftar hanya dilaporkan. Untuk menghapusnya (beserta harga & prediksi
DUMMY-nya), tambahkan --hapus-di-luar-daftar. Wilayah yang punya data asli (bukan dummy) tidak akan dihapus.

Cara menjalankan (dari folder sempol-backend):
    python -m scripts.seed_wilayah
    python -m scripts.seed_wilayah --hapus-di-luar-daftar
"""

import sys

from sqlmodel import Session, col, delete, func, select

from app.models import HargaHarian, PrediksiHarga, Wilayah

DATA_WILAYAH = [
    # (kode, nama, provinsi, lat, lng)  # nama kota sampel PIHPS kalau berbeda
    ("11.05", "Kabupaten Aceh Barat", "Aceh", 4.1530, 96.1314),  # Meulaboh
    ("11.71", "Kota Banda Aceh", "Aceh", 5.5500, 95.3178),
    ("11.73", "Kota Lhokseumawe", "Aceh", 5.1794, 97.1489),
    ("12.71", "Kota Medan", "Sumatera Utara", 3.5902, 98.6750),
    ("12.72", "Kota Pematangsiantar", "Sumatera Utara", 2.9565, 99.0618),
    ("12.73", "Kota Sibolga", "Sumatera Utara", 1.7460, 98.7756),
    ("12.77", "Kota Padangsidimpuan", "Sumatera Utara", 1.3776, 99.2714),
    ("13.71", "Kota Padang", "Sumatera Barat", -0.8759, 100.3873),
    ("13.75", "Kota Bukittinggi", "Sumatera Barat", -0.2855, 100.3678),
    ("14.04", "Kabupaten Indragiri Hilir", "Riau", -0.3152, 103.1579),  # Tembilahan
    ("14.71", "Kota Pekanbaru", "Riau", 0.5134, 101.4470),
    ("14.72", "Kota Dumai", "Riau", 1.6054, 101.3917),
    ("15.08", "Kabupaten Bungo", "Jambi", -1.5163, 102.1187),  # Muara Bungo
    ("15.71", "Kota Jambi", "Jambi", -1.6305, 103.6073),
    ("16.71", "Kota Palembang", "Sumatera Selatan", -2.9910, 104.7568),
    ("16.73", "Kota Lubuk Linggau", "Sumatera Selatan", -3.3258, 102.8254),
    ("17.71", "Kota Bengkulu", "Bengkulu", -3.7928, 102.2608),
    ("18.71", "Kota Bandar Lampung", "Lampung", -5.4296, 105.2626),
    ("18.72", "Kota Metro", "Lampung", -5.1137, 105.3069),
    ("19.02", "Kabupaten Belitung", "Kepulauan Bangka Belitung", -2.7423, 107.6543),  # Tanjung Pandan
    ("19.71", "Kota Pangkal Pinang", "Kepulauan Bangka Belitung", -2.1410, 106.1159),
    ("21.71", "Kota Batam", "Kepulauan Riau", 1.1287, 104.0553),
    ("21.72", "Kota Tanjung Pinang", "Kepulauan Riau", 0.9653, 104.4410),
    ("31.71", "Kota Administrasi Jakarta Pusat", "DKI Jakarta", -6.1729, 106.8187),
    ("31.72", "Kota Administrasi Jakarta Utara", "DKI Jakarta", -6.1200, 106.8925),
    ("31.73", "Kota Administrasi Jakarta Barat", "DKI Jakarta", -6.1843, 106.7366),
    ("31.74", "Kota Administrasi Jakarta Selatan", "DKI Jakarta", -6.2478, 106.8076),
    ("31.75", "Kota Administrasi Jakarta Timur", "DKI Jakarta", -6.2137, 106.9440),
    ("32.71", "Kota Bogor", "Jawa Barat", -6.5951, 106.7941),
    ("32.72", "Kota Sukabumi", "Jawa Barat", -6.9176, 106.9319),
    ("32.73", "Kota Bandung", "Jawa Barat", -6.9107, 107.6099),
    ("32.74", "Kota Cirebon", "Jawa Barat", -6.7067, 108.5582),
    ("32.75", "Kota Bekasi", "Jawa Barat", -6.2360, 106.9942),
    ("32.76", "Kota Depok", "Jawa Barat", -6.3942, 106.8227),
    ("32.78", "Kota Tasikmalaya", "Jawa Barat", -7.3161, 108.1970),
    ("33.01", "Kabupaten Cilacap", "Jawa Tengah", -7.7256, 109.0095),
    ("33.02", "Kabupaten Banyumas", "Jawa Tengah", -7.4228, 109.2301),  # Purwokerto
    ("33.19", "Kabupaten Kudus", "Jawa Tengah", -6.8057, 110.8422),
    ("33.72", "Kota Surakarta", "Jawa Tengah", -7.5693, 110.8295),
    ("33.74", "Kota Semarang", "Jawa Tengah", -6.9817, 110.4122),
    ("33.76", "Kota Tegal", "Jawa Tengah", -6.8704, 109.1374),
    ("34.71", "Kota Yogyakarta", "DI Yogyakarta", -7.7999, 110.3914),
    ("35.09", "Kabupaten Jember", "Jawa Timur", -8.1697, 113.7022),
    ("35.10", "Kabupaten Banyuwangi", "Jawa Timur", -8.2230, 114.3664),
    ("35.29", "Kabupaten Sumenep", "Jawa Timur", -7.0140, 113.8635),
    ("35.71", "Kota Kediri", "Jawa Timur", -7.8122, 112.0143),
    ("35.73", "Kota Malang", "Jawa Timur", -7.9778, 112.6338),
    ("35.74", "Kota Probolinggo", "Jawa Timur", -7.7537, 113.2142),
    ("35.77", "Kota Madiun", "Jawa Timur", -7.6244, 111.5206),
    ("35.78", "Kota Surabaya", "Jawa Timur", -7.2589, 112.7470),
    ("36.71", "Kota Tangerang", "Banten", -6.1644, 106.6411),
    ("36.72", "Kota Cilegon", "Banten", -6.0098, 106.0421),
    ("36.73", "Kota Serang", "Banten", -6.1197, 106.1735),
    ("51.08", "Kabupaten Buleleng", "Bali", -8.1252, 115.0928),  # Singaraja
    ("51.71", "Kota Denpasar", "Bali", -8.6545, 115.2165),
    ("52.71", "Kota Mataram", "Nusa Tenggara Barat", -8.5827, 116.1081),
    ("52.72", "Kota Bima", "Nusa Tenggara Barat", -8.4617, 118.7487),
    ("53.07", "Kabupaten Sikka", "Nusa Tenggara Timur", -8.6166, 122.2081),  # Maumere
    ("53.71", "Kota Kupang", "Nusa Tenggara Timur", -10.1539, 123.6194),
    ("61.71", "Kota Pontianak", "Kalimantan Barat", -0.0221, 109.3381),
    ("61.72", "Kota Singkawang", "Kalimantan Barat", 0.9048, 108.9774),
    ("62.02", "Kabupaten Kotawaringin Timur", "Kalimantan Tengah", -2.5375, 112.9410),  # Sampit
    ("62.71", "Kota Palangkaraya", "Kalimantan Tengah", -2.1740, 113.8803),
    ("63.09", "Kabupaten Tabalong", "Kalimantan Selatan", -2.1644, 115.3824),  # Tanjung
    ("63.71", "Kota Banjarmasin", "Kalimantan Selatan", -3.3275, 114.5890),
    ("64.71", "Kota Balikpapan", "Kalimantan Timur", -1.2763, 116.8278),
    ("64.72", "Kota Samarinda", "Kalimantan Timur", -0.4914, 117.1460),
    ("65.71", "Kota Tarakan", "Kalimantan Utara", 3.3137, 117.6049),
    ("71.71", "Kota Manado", "Sulawesi Utara", 1.4846, 124.8491),
    ("72.71", "Kota Palu", "Sulawesi Tengah", -0.9000, 119.8910),
    ("73.02", "Kabupaten Bulukumba", "Sulawesi Selatan", -5.5582, 120.1931),
    ("73.08", "Kabupaten Bone", "Sulawesi Selatan", -4.5393, 120.3093),  # Watampone
    ("73.71", "Kota Makassar", "Sulawesi Selatan", -5.1332, 119.4078),
    ("73.72", "Kota Parepare", "Sulawesi Selatan", -4.0278, 119.6333),
    ("73.73", "Kota Palopo", "Sulawesi Selatan", -3.0084, 120.2016),
    ("74.71", "Kota Kendari", "Sulawesi Tenggara", -3.9729, 122.5117),
    ("74.72", "Kota Bau Bau", "Sulawesi Tenggara", -5.4851, 122.5848),
    ("75.71", "Kota Gorontalo", "Gorontalo", 0.5319, 123.0595),
    ("76.02", "Kabupaten Mamuju", "Sulawesi Barat", -2.6897, 118.8845),
    ("81.71", "Kota Ambon", "Maluku", -3.6943, 128.1813),
    ("81.72", "Kota Tual", "Maluku", -5.6347, 132.7517),
    ("82.71", "Kota Ternate", "Maluku Utara", 0.7858, 127.3878),
    ("91.71", "Kota Jayapura", "Papua", -2.5626, 140.6926),
    ("92.02", "Kabupaten Manokwari", "Papua Barat", -0.8908, 134.0401),
    ("93.01", "Kabupaten Merauke", "Papua Selatan", -8.5087, 140.4097),
    ("96.71", "Kota Sorong", "Papua Barat Daya", -0.8811, 131.2876),
]


def sinkronkan_wilayah(session: Session, data: list[tuple], hapus_di_luar_daftar: bool = False) -> dict:
    """Samakan tabel wilayah dengan `data`. Mengembalikan ringkasan untuk dicetak."""
    sudah_ada = {w.kode: w for w in session.exec(select(Wilayah)).all()}
    ringkasan = {"tambah": 0, "perbarui": 0, "di_luar_daftar": [], "dihapus": [], "tidak_dihapus": []}

    for kode, nama, provinsi, lat, lng in data:
        wilayah = sudah_ada.get(kode)
        if wilayah is None:
            wilayah = Wilayah(kode=kode)
            ringkasan["tambah"] += 1
        else:
            ringkasan["perbarui"] += 1
        wilayah.sqlmodel_update({"nama": nama, "provinsi": provinsi, "lat": lat, "lng": lng})
        session.add(wilayah)

    kode_daftar = {baris[0] for baris in data}
    for kode, wilayah in sorted(sudah_ada.items()):
        if kode in kode_daftar:
            continue
        ringkasan["di_luar_daftar"].append(f"{kode} {wilayah.nama}")
        if not hapus_di_luar_daftar:
            continue
        # pengaman: jangan hapus wilayah yang sudah punya data asli
        data_asli = session.exec(
            select(func.count()).select_from(HargaHarian).where(
                HargaHarian.wilayah_id == wilayah.id, HargaHarian.sumber != "dummy"
            )
        ).one() + session.exec(
            select(func.count()).select_from(PrediksiHarga).where(
                PrediksiHarga.wilayah_id == wilayah.id, PrediksiHarga.versi_model != "dummy"
            )
        ).one()
        if data_asli:
            ringkasan["tidak_dihapus"].append(f"{kode} {wilayah.nama} ({data_asli} data asli)")
            continue
        session.exec(delete(HargaHarian).where(col(HargaHarian.wilayah_id) == wilayah.id))
        session.exec(delete(PrediksiHarga).where(col(PrediksiHarga.wilayah_id) == wilayah.id))
        session.delete(wilayah)
        ringkasan["dihapus"].append(f"{kode} {wilayah.nama}")

    session.commit()
    return ringkasan


def main():
    from app.database import engine  # di sini, supaya tes bisa import fungsi di atas tanpa koneksi Neon

    hapus = "--hapus-di-luar-daftar" in sys.argv
    with Session(engine) as session:
        ringkasan = sinkronkan_wilayah(session, DATA_WILAYAH, hapus_di_luar_daftar=hapus)

    print(f"tambah {ringkasan['tambah']}, perbarui {ringkasan['perbarui']} wilayah")
    for judul, kunci in [
        ("dihapus (beserta harga & prediksi dummy)", "dihapus"),
        ("TIDAK dihapus karena punya data asli", "tidak_dihapus"),
    ]:
        if ringkasan[kunci]:
            print(f"{judul}: {', '.join(ringkasan[kunci])}")
    if ringkasan["di_luar_daftar"] and not hapus:
        print(f"di luar daftar (dibiarkan): {', '.join(ringkasan['di_luar_daftar'])}")
        print("jalankan dengan --hapus-di-luar-daftar untuk menghapusnya")


if __name__ == "__main__":
    main()
