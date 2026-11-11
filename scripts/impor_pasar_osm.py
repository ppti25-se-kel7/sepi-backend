"""Ambil lokasi pasar dari OpenStreetMap (lewat Overpass API) di sekitar setiap wilayah, simpan ke tabel pasar.

- Pasar tradisional = amenity=marketplace, pasar modern = shop=supermarket.
- Yang diambil: dalam radius 15 km dari titik pusat tiap wilayah, dan hanya yang punya nama.
- Aman dijalankan berulang kali: pasar yang osm_id-nya sudah ada akan diperbarui, bukan dibuat dobel.
- Data OpenStreetMap berlisensi ODbL: wajib mencantumkan "© OpenStreetMap contributors" (ada di respons API).
- Ada jeda antar permintaan supaya sopan ke server Overpass (layanan gratis).

Cara menjalankan (dari folder sempol-backend):
    python -m scripts.impor_pasar_osm              # semua wilayah
    python -m scripts.impor_pasar_osm 32.71 32.01  # wilayah tertentu saja
    python -m scripts.impor_pasar_osm --hanya-yang-kosong  # lanjutkan impor yang terputus
Kalau server Overpass sibuk, wilayah yang gagal dilewati dan didaftar di akhir untuk diulang.
"""

import json
import ssl
import sys
import time
import urllib.parse
import urllib.request

from sqlmodel import Session, select

from app.models import Pasar, Wilayah
from app.routers.wilayah import hitung_jarak_km

URL_OVERPASS = "https://overpass-api.de/api/interpreter"
RADIUS_METER = 15000
JEDA_DETIK = 2
NAMA_APLIKASI = "sepi-backend/0.1 (proyek mahasiswa, impor pasar sekali-sekali)"

# Daftar sertifikat HTTPS: pakai certifi kalau terpasang (di sebagian laptop Windows, daftar bawaan Python
# menolak sertifikat Overpass sebagai "expired"). Verifikasi HTTPS tetap aktif.
try:
    import certifi

    KONTEKS_SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    KONTEKS_SSL = ssl.create_default_context()


def buat_query(lat: float, lng: float) -> str:
    sekitar = f"(around:{RADIUS_METER},{lat},{lng})"
    return (
        "[out:json][timeout:90];"
        f'(nwr["amenity"="marketplace"]{sekitar};nwr["shop"="supermarket"]{sekitar};);'
        "out center tags;"
    )


def ambil_dari_overpass(query: str, percobaan: int = 4) -> list[dict]:
    data = urllib.parse.urlencode({"data": query}).encode()
    for ke in range(1, percobaan + 1):
        permintaan = urllib.request.Request(URL_OVERPASS, data=data, headers={"User-Agent": NAMA_APLIKASI})
        try:
            with urllib.request.urlopen(permintaan, timeout=120, context=KONTEKS_SSL) as respons:
                return json.load(respons)["elements"]
        except Exception as e:  # server sibuk (429/504) → tunggu lalu coba lagi
            if ke == percobaan:
                raise
            print(f"  gagal ({e}), coba lagi dalam {JEDA_DETIK * 15 * ke} detik", flush=True)
            time.sleep(JEDA_DETIK * 15 * ke)
    return []


def ubah_elemen_osm(elemen: dict) -> dict | None:
    """Ubah satu elemen Overpass jadi data pasar. None kalau tidak dipakai (tanpa nama/koordinat)."""
    tag = elemen.get("tags", {})
    nama = (tag.get("name") or "").strip()
    if not nama:
        return None
    if tag.get("amenity") == "marketplace":
        jenis = "tradisional"
    elif tag.get("shop") == "supermarket":
        jenis = "modern"
    else:
        return None
    titik = elemen if "lat" in elemen else elemen.get("center")  # node punya lat/lon; way/relation punya center
    if not titik:
        return None
    alamat = ", ".join(tag[k] for k in ("addr:street", "addr:city") if tag.get(k)) or None
    return {
        "osm_id": f"{elemen['type']}/{elemen['id']}",
        "nama": nama,
        "jenis": jenis,
        "lat": titik["lat"],
        "lng": titik["lon"],
        "alamat": alamat,
    }


def simpan_pasar(session: Session, daftar: list[dict], semua_wilayah: list[Wilayah]) -> tuple[int, int]:
    """Upsert berdasarkan osm_id. Wilayah pasar = wilayah dengan titik pusat terdekat."""
    sudah_ada = {
        p.osm_id: p
        for p in session.exec(select(Pasar).where(Pasar.osm_id.in_([d["osm_id"] for d in daftar]))).all()
    }
    tambah = perbarui = 0
    for data in {d["osm_id"]: d for d in daftar}.values():  # buang dobel di dalam satu impor
        wilayah = min(semua_wilayah, key=lambda w: hitung_jarak_km(data["lat"], data["lng"], w.lat, w.lng))
        pasar = sudah_ada.get(data["osm_id"])
        if pasar is None:
            pasar = Pasar(**data, wilayah_id=wilayah.id)
            tambah += 1
        else:
            pasar.sqlmodel_update({**data, "wilayah_id": wilayah.id})
            perbarui += 1
        session.add(pasar)
    session.commit()
    return tambah, perbarui


def main():
    from app.database import engine  # di sini, supaya tes bisa import fungsi di atas tanpa koneksi Neon

    hanya_yang_kosong = "--hanya-yang-kosong" in sys.argv
    pilihan = {arg for arg in sys.argv[1:] if not arg.startswith("--")}
    with Session(engine) as session:
        semua_wilayah = session.exec(select(Wilayah).order_by(Wilayah.kode)).all()
        target = [w for w in semua_wilayah if not pilihan or w.kode in pilihan]
        if hanya_yang_kosong:  # lanjutkan impor yang terputus: lewati wilayah yang sudah punya data pasar
            sudah_ada = set(session.exec(select(Pasar.wilayah_id).distinct()).all())
            target = [w for w in target if w.id not in sudah_ada]

        total_tambah = total_perbarui = 0
        gagal = []
        for nomor, wilayah in enumerate(target, start=1):
            try:
                elemen = ambil_dari_overpass(buat_query(wilayah.lat, wilayah.lng))
            except Exception as e:  # server Overpass sibuk terus: catat, lanjut ke wilayah berikutnya
                gagal.append(wilayah.kode)
                print(f"[{nomor}/{len(target)}] {wilayah.kode} {wilayah.nama}: GAGAL ({e})", flush=True)
                continue
            daftar = [d for d in map(ubah_elemen_osm, elemen) if d]
            tambah, perbarui = simpan_pasar(session, daftar, semua_wilayah)
            total_tambah, total_perbarui = total_tambah + tambah, total_perbarui + perbarui
            print(f"[{nomor}/{len(target)}] {wilayah.kode} {wilayah.nama}: {len(daftar)} pasar "
                  f"(tambah {tambah}, perbarui {perbarui})", flush=True)
            time.sleep(JEDA_DETIK)
    print(f"selesai: tambah {total_tambah}, perbarui {total_perbarui} pasar")
    if gagal:
        print(f"gagal {len(gagal)} wilayah: {' '.join(gagal)}")
        print(f"ulangi nanti: python -m scripts.impor_pasar_osm {' '.join(gagal)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
