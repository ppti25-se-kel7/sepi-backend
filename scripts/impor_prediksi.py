"""Masukkan file CSV hasil model prediksi (Kay) ke tabel prediksi_harga.

Format CSV (baris pertama = nama kolom; harga_min & harga_max boleh kosong):
    komoditas,wilayah,jenis_pasar,tanggal_prediksi,harga,harga_min,harga_max,versi_model
    beras,32.01,tradisional,2026-11-11,15200,14800,15600,v1

- komoditas = label komoditas (mis. beras), wilayah = kode wilayah Kemendagri (mis. 32.01)
- jenis_pasar = tradisional / modern, tanggal_prediksi = YYYY-MM-DD, harga dalam rupiah (bilangan bulat)

Semua baris diperiksa dulu. Kalau ada satu saja yang salah, TIDAK ADA yang disimpan dan semua kesalahan
ditampilkan, supaya data di database tidak setengah-setengah. Prediksi yang sudah ada untuk
komoditas + wilayah + jenis pasar + tanggal yang sama akan ditimpa dengan yang baru.

Cara menjalankan (dari folder sempol-backend):
    python -m scripts.impor_prediksi path/ke/prediksi.csv
"""

import csv
import sys
from datetime import date, datetime, timezone

from sqlmodel import Session, col, select

from app.models import Komoditas, PrediksiHarga, Wilayah

KOLOM = ["komoditas", "wilayah", "jenis_pasar", "tanggal_prediksi", "harga", "harga_min", "harga_max", "versi_model"]
JENIS_PASAR = {"tradisional", "modern"}


class PrediksiTidakValid(Exception):
    def __init__(self, kesalahan: list[str]):
        super().__init__(f"{len(kesalahan)} baris tidak valid")
        self.kesalahan = kesalahan


def ambil(baris: dict, kolom: str) -> str:
    return (baris.get(kolom) or "").strip()


def ke_rupiah(teks: str, kolom: str) -> int:
    try:
        nilai = int(teks)
    except ValueError:
        raise ValueError(f"{kolom} harus bilangan bulat, bukan '{teks}'")
    if nilai <= 0:
        raise ValueError(f"{kolom} harus lebih dari 0")
    return nilai


def periksa_baris(baris: dict, komoditas_id: dict, wilayah_id: dict) -> tuple[tuple, dict]:
    """Ubah satu baris CSV jadi (kunci, isi). Lempar ValueError berisi pesan yang jelas kalau salah."""
    label, kode, jenis_pasar = ambil(baris, "komoditas"), ambil(baris, "wilayah"), ambil(baris, "jenis_pasar")
    if label not in komoditas_id:
        raise ValueError(f"komoditas '{label}' tidak ada di tabel komoditas")
    if kode not in wilayah_id:
        raise ValueError(f"wilayah '{kode}' tidak ada di tabel wilayah")
    if jenis_pasar not in JENIS_PASAR:
        raise ValueError(f"jenis_pasar harus tradisional/modern, bukan '{jenis_pasar}'")
    try:
        tanggal = date.fromisoformat(ambil(baris, "tanggal_prediksi"))
    except ValueError:
        raise ValueError(f"tanggal_prediksi harus format YYYY-MM-DD, bukan '{ambil(baris, 'tanggal_prediksi')}'")

    harga = ke_rupiah(ambil(baris, "harga"), "harga")
    harga_min = ke_rupiah(ambil(baris, "harga_min"), "harga_min") if ambil(baris, "harga_min") else None
    harga_max = ke_rupiah(ambil(baris, "harga_max"), "harga_max") if ambil(baris, "harga_max") else None
    if harga_min is not None and harga_min > harga:
        raise ValueError("harga_min tidak boleh lebih besar dari harga")
    if harga_max is not None and harga_max < harga:
        raise ValueError("harga_max tidak boleh lebih kecil dari harga")
    versi_model = ambil(baris, "versi_model")
    if not versi_model:
        raise ValueError("versi_model wajib diisi")

    kunci = (komoditas_id[label], wilayah_id[kode], jenis_pasar, tanggal)
    isi = {"harga": harga, "harga_min": harga_min, "harga_max": harga_max, "versi_model": versi_model}
    return kunci, isi


def impor_prediksi(session: Session, daftar_baris: list[dict]) -> tuple[int, int]:
    """Simpan semua baris kalau semuanya valid. Mengembalikan (jumlah ditambah, jumlah diperbarui)."""
    komoditas_id = {k.label: k.id for k in session.exec(select(Komoditas)).all()}
    wilayah_id = {w.kode: w.id for w in session.exec(select(Wilayah)).all()}

    data, kesalahan = {}, []
    for nomor, baris in enumerate(daftar_baris, start=2):  # baris 1 di file = nama kolom
        try:
            kunci, isi = periksa_baris(baris, komoditas_id, wilayah_id)
        except ValueError as e:
            kesalahan.append(f"baris {nomor}: {e}")
            continue
        if kunci in data:
            kesalahan.append(f"baris {nomor}: dobel (komoditas, wilayah, jenis pasar, dan tanggal sama dengan baris lain)")
            continue
        data[kunci] = isi
    if kesalahan:
        raise PrediksiTidakValid(kesalahan)

    # ambil prediksi lama untuk tanggal-tanggal ini sekaligus, supaya tidak query satu per satu ke Neon
    semua_tanggal = {kunci[3] for kunci in data}
    sudah_ada = {
        (p.komoditas_id, p.wilayah_id, p.jenis_pasar, p.tanggal_prediksi): p
        for p in session.exec(
            select(PrediksiHarga).where(col(PrediksiHarga.tanggal_prediksi).in_(semua_tanggal))
        ).all()
    }

    jumlah_tambah = jumlah_perbarui = 0
    sekarang = datetime.now(timezone.utc)
    for (komoditas, wilayah, jenis_pasar, tanggal), isi in data.items():
        prediksi = sudah_ada.get((komoditas, wilayah, jenis_pasar, tanggal))
        if prediksi is None:
            prediksi = PrediksiHarga(
                komoditas_id=komoditas, wilayah_id=wilayah, jenis_pasar=jenis_pasar, tanggal_prediksi=tanggal, **isi
            )
            jumlah_tambah += 1
        else:
            prediksi.sqlmodel_update(isi)
            jumlah_perbarui += 1
        prediksi.dibuat_pada = sekarang
        session.add(prediksi)
    session.commit()
    return jumlah_tambah, jumlah_perbarui


def main():
    from app.database import engine  # di sini, supaya tes bisa import fungsi di atas tanpa koneksi Neon

    if len(sys.argv) != 2:
        print("Cara pakai: python -m scripts.impor_prediksi path/ke/prediksi.csv")
        sys.exit(1)

    # utf-8-sig: tetap terbaca walau file disimpan dari Excel (ada BOM di awal file)
    with open(sys.argv[1], encoding="utf-8-sig", newline="") as file:
        pembaca = csv.DictReader(file)
        kolom_kurang = [k for k in KOLOM if k not in (pembaca.fieldnames or [])]
        if kolom_kurang:
            print(f"Kolom tidak lengkap, kurang: {', '.join(kolom_kurang)}")
            sys.exit(1)
        daftar_baris = list(pembaca)

    with Session(engine) as session:
        try:
            tambah, perbarui = impor_prediksi(session, daftar_baris)
        except PrediksiTidakValid as e:
            print(f"Tidak ada yang disimpan, {len(e.kesalahan)} baris salah:")
            for pesan in e.kesalahan:
                print(f"  - {pesan}")
            sys.exit(1)
    print(f"tambah {tambah}, perbarui {perbarui} prediksi")


if __name__ == "__main__":
    main()
