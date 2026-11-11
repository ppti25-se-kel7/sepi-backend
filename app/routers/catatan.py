"""Catatan belanja (wajib login).

Contoh: Budi disuruh istrinya ke pasar. Ia mencatat barang + jumlahnya, dan aplikasi menampilkan
perkiraan harga supaya Budi tahu kisaran uang yang perlu dibawa dan tidak lupa barangnya.

Harga tiap barang dihitung SAAT DIBACA (bukan disimpan), jadi selalu mengikuti prediksi terbaru:
- harga diisi user (harga_manual)     → dipakai apa adanya, tidak ikut berubah
- barang dari daftar komoditas        → prediksi harga × jumlah (kalau satuannya bisa dikonversi)
- barang ketik sendiri / satuan bebas → harga perlu diisi user sendiri
"""

from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import model_validator
from sqlalchemy import Integer, cast
from sqlmodel import Field, Session, SQLModel, col, delete, func, select

from app.auth import PenggunaDep
from app.database import SessionDep
from app.errors import AppError, ErrorResponse
from app.models import (
    Catatan,
    CatatanItem,
    Komoditas,
    KomoditasRingkas,
    Pengguna,
    PrediksiHarga,
    Wilayah,
    WilayahRingkas,
)
from app.routers import prediksi  # prediksi.hari_ini() → tanggal hari ini (WIB)

router = APIRouter(prefix="/catatan", tags=["catatan belanja"])

# faktor untuk mengubah satuan barang ke satuan komoditas (mis. 250 gram → 0,25 kg)
KONVERSI_SATUAN = {
    "kg": {"kg": 1, "kilo": 1, "kilogram": 1, "ons": 0.1, "g": 0.001, "gr": 0.001, "gram": 0.001},
    "liter": {"liter": 1, "l": 1, "ml": 0.001},
}

ERROR_LOGIN = {
    401: {"model": ErrorResponse, "description": "`BELUM_LOGIN` atau `TOKEN_TIDAK_VALID`"},
}
ERROR_TIDAK_DITEMUKAN = {
    404: {"model": ErrorResponse, "description": "`CATATAN_TIDAK_DITEMUKAN`, `ITEM_TIDAK_DITEMUKAN`, "
          "`KOMODITAS_TIDAK_DITEMUKAN`, atau `WILAYAH_TIDAK_DITEMUKAN`"},
    422: {"model": ErrorResponse, "description": "`INPUT_TIDAK_VALID`"},
}


# ---------- bentuk request ----------

class CatatanBuat(SQLModel):
    judul: str = Field(min_length=1, max_length=100)
    wilayah: str | None = None  # kode wilayah, mis. "32.71"; untuk harga prediksi
    jenis_pasar: Literal["tradisional", "modern"] = "tradisional"


class CatatanUbah(SQLModel):
    # semua opsional: hanya field yang dikirim yang diubah; kirim "wilayah": null untuk mengosongkan
    judul: str | None = Field(default=None, min_length=1, max_length=100)
    wilayah: str | None = None
    jenis_pasar: Literal["tradisional", "modern"] | None = None


class ItemBuat(SQLModel):
    komoditas: str | None = None  # label dari daftar komoditas, mis. "bawang_merah"
    nama: str | None = Field(default=None, max_length=100)  # atau ketik sendiri, mis. "kerupuk"
    jumlah: float = Field(gt=0)  # 1/4 kg → 0.25
    satuan: str = Field(min_length=1, max_length=30)
    harga_manual: int | None = Field(default=None, ge=0)  # total harga barang ini, kalau diisi sendiri

    @model_validator(mode="after")
    def komoditas_atau_nama(self):
        if (self.komoditas is None) == (self.nama is None or not self.nama.strip()):
            raise ValueError("isi salah satu: komoditas (dari daftar) atau nama (ketik sendiri)")
        return self


class ItemUbah(SQLModel):
    jumlah: float | None = Field(default=None, gt=0)
    satuan: str | None = Field(default=None, min_length=1, max_length=30)
    harga_manual: int | None = Field(default=None, ge=0)  # kirim null untuk kembali ke harga prediksi
    sudah_dibeli: bool | None = None


# ---------- bentuk respons ----------

class ItemPublik(SQLModel):
    id: int
    komoditas: KomoditasRingkas | None  # null kalau nama diketik sendiri
    nama: str
    jumlah: float
    satuan: str
    sudah_dibeli: bool
    harga_manual: int | None
    # status_harga: "manual" | "prediksi" | "isi_manual" (barang ketik sendiri) | "satuan_tidak_bisa_dihitung"
    #               | "wilayah_belum_dipilih" | "prediksi_belum_tersedia"
    status_harga: str
    harga_perkiraan: int | None  # total untuk jumlah ini; null kalau belum bisa dihitung
    harga_min: int | None
    harga_max: int | None
    tanggal_prediksi: date | None


class CatatanDetail(SQLModel):
    id: int
    judul: str
    wilayah: WilayahRingkas | None
    jenis_pasar: str
    dibuat_pada: datetime
    diubah_pada: datetime
    item: list[ItemPublik]
    jumlah_item: int
    jumlah_sudah_dibeli: int
    item_tanpa_harga: int  # barang yang harganya belum bisa dihitung (perlu diisi manual)
    total_perkiraan: int  # jumlah semua harga_perkiraan yang ada
    total_min: int
    total_max: int


class CatatanRingkas(SQLModel):
    id: int
    judul: str
    wilayah: WilayahRingkas | None
    jenis_pasar: str
    jumlah_item: int
    jumlah_sudah_dibeli: int
    diubah_pada: datetime


# ---------- fungsi bantu ----------

def jumlah_dalam_satuan_komoditas(jumlah: float, satuan_item: str, satuan_komoditas: str) -> float | None:
    """250 gram & komoditas per kg → 0,25. Kembalikan None kalau tidak bisa dikonversi (mis. kresek)."""
    item, dasar = satuan_item.strip().lower(), satuan_komoditas.strip().lower()
    if item == dasar:
        return jumlah
    faktor = KONVERSI_SATUAN.get(dasar, {}).get(item)
    return None if faktor is None else jumlah * faktor


def bulatkan_ratusan(nilai: float) -> int:
    # pembulatan biasa (4.250 → 4.300); round() Python membulatkan .5 ke angka genap (4.250 → 4.200)
    return int(nilai / 100 + 0.5) * 100


def cari_wilayah(session: Session, kode: str | None) -> Wilayah | None:
    if kode is None:
        return None
    wilayah = session.exec(select(Wilayah).where(Wilayah.kode == kode)).first()
    if wilayah is None:
        raise AppError(404, "WILAYAH_TIDAK_DITEMUKAN", "Wilayah tidak ditemukan")
    return wilayah


def ambil_catatan(session: Session, pengguna: Pengguna, catatan_id: int) -> Catatan:
    catatan = session.get(Catatan, catatan_id)
    # catatan milik orang lain dianggap tidak ada (404), supaya tidak bocor bahwa id itu ada
    if catatan is None or catatan.pengguna_id != pengguna.id:
        raise AppError(404, "CATATAN_TIDAK_DITEMUKAN", "Catatan tidak ditemukan")
    return catatan


def ambil_item(session: Session, catatan: Catatan, item_id: int) -> CatatanItem:
    item = session.get(CatatanItem, item_id)
    if item is None or item.catatan_id != catatan.id:
        raise AppError(404, "ITEM_TIDAK_DITEMUKAN", "Barang tidak ditemukan di catatan ini")
    return item


def tandai_diubah(session: Session, catatan: Catatan):
    catatan.diubah_pada = datetime.now(timezone.utc)
    session.add(catatan)
    session.commit()


def susun_detail(session: Session, catatan: Catatan) -> CatatanDetail:
    """Gabungkan catatan + barang + harga prediksi terbaru menjadi satu respons."""
    daftar_item = session.exec(
        select(CatatanItem).where(CatatanItem.catatan_id == catatan.id).order_by(col(CatatanItem.id))
    ).all()
    wilayah = session.get(Wilayah, catatan.wilayah_id) if catatan.wilayah_id else None
    komoditas = {
        k.id: k
        for k in session.exec(
            select(Komoditas).where(col(Komoditas.id).in_([i.komoditas_id for i in daftar_item if i.komoditas_id]))
        ).all()
    }

    # prediksi terdekat mulai hari ini untuk tiap komoditas (satu query untuk semua barang)
    prediksi_terdekat = {}
    if wilayah and komoditas:
        for p in session.exec(
            select(PrediksiHarga)
            .where(
                PrediksiHarga.wilayah_id == wilayah.id,
                PrediksiHarga.jenis_pasar == catatan.jenis_pasar,
                col(PrediksiHarga.komoditas_id).in_(list(komoditas)),
                col(PrediksiHarga.tanggal_prediksi) >= prediksi.hari_ini(),
            )
            .order_by(col(PrediksiHarga.tanggal_prediksi).desc())
        ).all():
            prediksi_terdekat[p.komoditas_id] = p  # urut menurun → yang tersisa = tanggal paling dekat

    hasil = []
    for item in daftar_item:
        k = komoditas.get(item.komoditas_id)
        harga = harga_min = harga_max = tanggal = None
        if item.harga_manual is not None:
            status, harga = "manual", item.harga_manual
            harga_min = harga_max = harga
        elif k is None:
            status = "isi_manual"
        elif (jumlah := jumlah_dalam_satuan_komoditas(item.jumlah, item.satuan, k.satuan)) is None:
            status = "satuan_tidak_bisa_dihitung"
        elif wilayah is None:
            status = "wilayah_belum_dipilih"
        elif (p := prediksi_terdekat.get(k.id)) is None:
            status = "prediksi_belum_tersedia"
        else:
            status = "prediksi"
            harga = bulatkan_ratusan(p.harga * jumlah)
            harga_min = bulatkan_ratusan((p.harga_min or p.harga) * jumlah)
            harga_max = bulatkan_ratusan((p.harga_max or p.harga) * jumlah)
            tanggal = p.tanggal_prediksi
        hasil.append(
            ItemPublik(
                id=item.id,
                komoditas=KomoditasRingkas.model_validate(k) if k else None,
                nama=k.nama if k else item.nama_bebas,
                jumlah=item.jumlah,
                satuan=item.satuan,
                sudah_dibeli=item.sudah_dibeli,
                harga_manual=item.harga_manual,
                status_harga=status,
                harga_perkiraan=harga,
                harga_min=harga_min,
                harga_max=harga_max,
                tanggal_prediksi=tanggal,
            )
        )

    berharga = [i for i in hasil if i.harga_perkiraan is not None]
    return CatatanDetail(
        id=catatan.id,
        judul=catatan.judul,
        wilayah=WilayahRingkas.model_validate(wilayah) if wilayah else None,
        jenis_pasar=catatan.jenis_pasar,
        dibuat_pada=catatan.dibuat_pada,
        diubah_pada=catatan.diubah_pada,
        item=hasil,
        jumlah_item=len(hasil),
        jumlah_sudah_dibeli=sum(i.sudah_dibeli for i in hasil),
        item_tanpa_harga=len(hasil) - len(berharga),
        total_perkiraan=sum(i.harga_perkiraan for i in berharga),
        total_min=sum(i.harga_min for i in berharga),
        total_max=sum(i.harga_max for i in berharga),
    )


# ---------- endpoint catatan ----------

@router.get("", response_model=list[CatatanRingkas], responses=ERROR_LOGIN)
def daftar_catatan(session: SessionDep, pengguna: PenggunaDep):
    """Semua catatan milik user yang login, yang terakhir diubah paling atas."""
    semua = session.exec(
        select(Catatan).where(Catatan.pengguna_id == pengguna.id).order_by(col(Catatan.diubah_pada).desc())
    ).all()
    hitungan = {
        catatan_id: (jumlah, dibeli)
        for catatan_id, jumlah, dibeli in session.exec(
            select(CatatanItem.catatan_id, func.count(), func.sum(cast(CatatanItem.sudah_dibeli, Integer)))
            .where(col(CatatanItem.catatan_id).in_([c.id for c in semua]))
            .group_by(CatatanItem.catatan_id)
        ).all()
    }
    id_wilayah = [c.wilayah_id for c in semua if c.wilayah_id]
    wilayah = {w.id: w for w in session.exec(select(Wilayah).where(col(Wilayah.id).in_(id_wilayah))).all()}
    return [
        CatatanRingkas(
            id=c.id,
            judul=c.judul,
            wilayah=WilayahRingkas.model_validate(wilayah[c.wilayah_id]) if c.wilayah_id else None,
            jenis_pasar=c.jenis_pasar,
            jumlah_item=hitungan.get(c.id, (0, 0))[0],
            jumlah_sudah_dibeli=hitungan.get(c.id, (0, 0))[1] or 0,
            diubah_pada=c.diubah_pada,
        )
        for c in semua
    ]


@router.post("", response_model=CatatanDetail, status_code=201, responses=ERROR_LOGIN | ERROR_TIDAK_DITEMUKAN)
def buat_catatan(data: CatatanBuat, session: SessionDep, pengguna: PenggunaDep):
    """Buat catatan baru. `wilayah` (kode) dipakai untuk menghitung harga prediksi barang."""
    wilayah = cari_wilayah(session, data.wilayah)
    catatan = Catatan(
        pengguna_id=pengguna.id,
        judul=data.judul.strip(),
        wilayah_id=wilayah.id if wilayah else None,
        jenis_pasar=data.jenis_pasar,
    )
    session.add(catatan)
    session.commit()
    session.refresh(catatan)
    return susun_detail(session, catatan)


@router.get("/{catatan_id}", response_model=CatatanDetail, responses=ERROR_LOGIN | ERROR_TIDAK_DITEMUKAN)
def detail_catatan(catatan_id: int, session: SessionDep, pengguna: PenggunaDep):
    """Isi catatan lengkap dengan perkiraan harga terbaru tiap barang dan totalnya."""
    return susun_detail(session, ambil_catatan(session, pengguna, catatan_id))


@router.patch("/{catatan_id}", response_model=CatatanDetail, responses=ERROR_LOGIN | ERROR_TIDAK_DITEMUKAN)
def ubah_catatan(catatan_id: int, data: CatatanUbah, session: SessionDep, pengguna: PenggunaDep):
    """Ubah judul, wilayah, atau jenis pasar. Hanya field yang dikirim yang diubah."""
    catatan = ambil_catatan(session, pengguna, catatan_id)
    perubahan = data.model_dump(exclude_unset=True)
    if perubahan.get("judul") is not None:
        catatan.judul = perubahan["judul"].strip()
    if perubahan.get("jenis_pasar") is not None:
        catatan.jenis_pasar = perubahan["jenis_pasar"]
    if "wilayah" in perubahan:
        wilayah = cari_wilayah(session, perubahan["wilayah"])
        catatan.wilayah_id = wilayah.id if wilayah else None
    tandai_diubah(session, catatan)
    return susun_detail(session, catatan)


@router.delete("/{catatan_id}", status_code=204, responses=ERROR_LOGIN | ERROR_TIDAK_DITEMUKAN)
def hapus_catatan(catatan_id: int, session: SessionDep, pengguna: PenggunaDep):
    """Hapus catatan beserta semua barangnya."""
    catatan = ambil_catatan(session, pengguna, catatan_id)
    session.exec(delete(CatatanItem).where(col(CatatanItem.catatan_id) == catatan.id))
    session.delete(catatan)
    session.commit()
    return Response(status_code=204)


# ---------- endpoint barang di dalam catatan ----------

@router.post(
    "/{catatan_id}/item", response_model=CatatanDetail, status_code=201,
    responses=ERROR_LOGIN | ERROR_TIDAK_DITEMUKAN,
)
def tambah_item(catatan_id: int, data: ItemBuat, session: SessionDep, pengguna: PenggunaDep):
    """Tambah barang: `komoditas` (label dari daftar) ATAU `nama` (ketik sendiri), plus jumlah & satuan.

    Mengembalikan catatan lengkap supaya Flutter bisa langsung memperbarui total.
    """
    catatan = ambil_catatan(session, pengguna, catatan_id)
    komoditas_id = None
    if data.komoditas is not None:
        komoditas = session.exec(select(Komoditas).where(Komoditas.label == data.komoditas)).first()
        if komoditas is None:
            raise AppError(404, "KOMODITAS_TIDAK_DITEMUKAN", "Komoditas tidak ditemukan")
        komoditas_id = komoditas.id
    session.add(
        CatatanItem(
            catatan_id=catatan.id,
            komoditas_id=komoditas_id,
            nama_bebas=data.nama.strip() if komoditas_id is None else None,
            jumlah=data.jumlah,
            satuan=data.satuan.strip(),
            harga_manual=data.harga_manual,
        )
    )
    tandai_diubah(session, catatan)
    return susun_detail(session, catatan)


@router.patch(
    "/{catatan_id}/item/{item_id}", response_model=CatatanDetail, responses=ERROR_LOGIN | ERROR_TIDAK_DITEMUKAN
)
def ubah_item(catatan_id: int, item_id: int, data: ItemUbah, session: SessionDep, pengguna: PenggunaDep):
    """Ubah jumlah, satuan, harga manual, atau centang `sudah_dibeli`. Hanya field yang dikirim yang diubah."""
    catatan = ambil_catatan(session, pengguna, catatan_id)
    item = ambil_item(session, catatan, item_id)
    perubahan = data.model_dump(exclude_unset=True)
    for kolom in ("jumlah", "satuan", "sudah_dibeli"):
        if perubahan.get(kolom) is not None:
            setattr(item, kolom, perubahan[kolom].strip() if kolom == "satuan" else perubahan[kolom])
    if "harga_manual" in perubahan:  # null boleh: kembali ke harga prediksi
        item.harga_manual = perubahan["harga_manual"]
    session.add(item)
    tandai_diubah(session, catatan)
    return susun_detail(session, catatan)


@router.delete(
    "/{catatan_id}/item/{item_id}", response_model=CatatanDetail, responses=ERROR_LOGIN | ERROR_TIDAK_DITEMUKAN
)
def hapus_item(catatan_id: int, item_id: int, session: SessionDep, pengguna: PenggunaDep):
    """Hapus satu barang dari catatan. Mengembalikan catatan lengkap yang sudah diperbarui."""
    catatan = ambil_catatan(session, pengguna, catatan_id)
    session.delete(ambil_item(session, catatan, item_id))
    tandai_diubah(session, catatan)
    return susun_detail(session, catatan)
