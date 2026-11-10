from datetime import date, datetime, timezone

from sqlmodel import CheckConstraint, DateTime, Field, SQLModel, UniqueConstraint


class KomoditasBase(SQLModel):
    label: str = Field(unique=True, index=True)  # sama persis dengan label model CV, mis. "bawang_merah"
    nama: str  # nama untuk ditampilkan, mis. "Bawang Merah"
    satuan: str  # mis. "kg", "liter"
    alias: str | None = None  # nama lain untuk pencarian, dipisah koma, mis. "cabe, cabe merah"


class Komoditas(KomoditasBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class KomoditasPublic(KomoditasBase):
    id: int


class WilayahBase(SQLModel):
    kode: str = Field(unique=True, index=True)  # kode wilayah Kemendagri, mis. "32.71"
    nama: str  # mis. "Kota Bogor"
    provinsi: str  # mis. "Jawa Barat"
    lat: float  # titik pusat kota / ibukota kabupaten (lintang)
    lng: float  # titik pusat kota / ibukota kabupaten (bujur)


class Wilayah(WilayahBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class WilayahPublic(WilayahBase):
    id: int


class WilayahTerdekat(WilayahPublic):
    jarak_km: float  # jarak garis lurus dari lokasi user ke titik pusat wilayah


class HargaHarian(SQLModel, table=True):
    __tablename__ = "harga_harian"
    __table_args__ = (
        # satu harga per komoditas, wilayah, jenis pasar, dan tanggal (juga mempercepat cari harga terbaru)
        UniqueConstraint("komoditas_id", "wilayah_id", "jenis_pasar", "tanggal", name="uq_harga_harian"),
        CheckConstraint("jenis_pasar IN ('tradisional', 'modern')", name="ck_harga_harian_jenis_pasar"),
    )

    id: int | None = Field(default=None, primary_key=True)
    tanggal: date
    komoditas_id: int = Field(foreign_key="komoditas.id")
    wilayah_id: int = Field(foreign_key="wilayah.id")
    jenis_pasar: str  # "tradisional" atau "modern"
    harga: int  # rupiah per satuan komoditas (rata-rata wilayah)
    sumber: str  # asal data, mis. "PIHPS", "dummy"


class KomoditasRingkas(SQLModel):
    label: str
    nama: str
    satuan: str


class WilayahRingkas(SQLModel):
    kode: str
    nama: str


class HargaPasar(SQLModel):
    status: str  # "tersedia" atau "belum_tersedia"
    harga: int | None = None  # null kalau belum tersedia, bukan 0
    tanggal: date | None = None
    sumber: str | None = None


class PerbandinganHarga(SQLModel):
    komoditas: KomoditasRingkas
    wilayah: WilayahRingkas
    keterangan: str = "rata-rata wilayah"
    tradisional: HargaPasar
    modern: HargaPasar


class RingkasanPasar(SQLModel):
    harga: int | None = None  # harga terbaru; null kalau belum ada data
    tanggal: date | None = None
    sumber: str | None = None
    prediksi_besok: int | None = None  # null kalau prediksi belum tersedia
    tren: str | None = None  # "naik" / "turun" / "stabil" (prediksi besok vs harga terbaru, batas ±2%)


class RingkasanKomoditas(SQLModel):
    komoditas: KomoditasRingkas
    tradisional: RingkasanPasar
    modern: RingkasanPasar


class RingkasanWilayah(SQLModel):
    # isi pop-up card saat wilayah di peta diklik: semua komoditas sekaligus
    wilayah: WilayahRingkas
    provinsi: str
    keterangan: str = "rata-rata wilayah"
    tanggal_prediksi: date  # tanggal "besok" yang dipakai untuk prediksi_besok
    komoditas: list[RingkasanKomoditas]


class PrediksiHarga(SQLModel, table=True):
    # hasil model prediksi Kay, dimasukkan lewat scripts/impor_prediksi.py
    __tablename__ = "prediksi_harga"
    __table_args__ = (
        # satu prediksi per komoditas, wilayah, jenis pasar, dan tanggal; impor ulang = menimpa dengan yang terbaru
        UniqueConstraint(
            "komoditas_id", "wilayah_id", "jenis_pasar", "tanggal_prediksi", name="uq_prediksi_harga"
        ),
        CheckConstraint("jenis_pasar IN ('tradisional', 'modern')", name="ck_prediksi_harga_jenis_pasar"),
        CheckConstraint(
            "harga > 0 AND (harga_min IS NULL OR harga_min <= harga) AND (harga_max IS NULL OR harga <= harga_max)",
            name="ck_prediksi_harga_rentang",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    komoditas_id: int = Field(foreign_key="komoditas.id")
    wilayah_id: int = Field(foreign_key="wilayah.id")
    jenis_pasar: str  # "tradisional" atau "modern"
    tanggal_prediksi: date  # tanggal yang diprediksi (bukan tanggal model dijalankan)
    harga: int  # perkiraan harga, rupiah per satuan komoditas
    harga_min: int | None = None  # batas bawah rentang perkiraan (opsional)
    harga_max: int | None = None  # batas atas rentang perkiraan (opsional)
    versi_model: str  # mis. "v1", "dummy"
    dibuat_pada: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )


class TitikPrediksi(SQLModel):
    tanggal: date
    harga: int
    harga_min: int | None
    harga_max: int | None
    versi_model: str


class PrediksiPasar(SQLModel):
    status: str  # "tersedia" atau "belum_tersedia"
    prediksi: list[TitikPrediksi] = []  # urut dari tanggal terdekat; kosong kalau belum tersedia


class PerbandinganPrediksi(SQLModel):
    komoditas: KomoditasRingkas
    wilayah: WilayahRingkas
    keterangan: str = "prediksi rata-rata wilayah"
    tradisional: PrediksiPasar
    modern: PrediksiPasar


class Pengguna(SQLModel, table=True):
    # data login dari Firebase; password tidak pernah disimpan di sini
    id: int | None = Field(default=None, primary_key=True)
    firebase_uid: str = Field(unique=True, index=True)  # id user dari Firebase (isi "sub" di token)
    email: str | None = None  # bisa kosong, mis. login dengan nomor HP
    nama: str | None = None
    dibuat_pada: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )


class PenggunaPublic(SQLModel):
    id: int
    email: str | None
    nama: str | None
    dibuat_pada: datetime


class Pasar(SQLModel, table=True):
    # lokasi pasar dari OpenStreetMap (scripts/impor_pasar_osm.py)
    __table_args__ = (CheckConstraint("jenis IN ('tradisional', 'modern')", name="ck_pasar_jenis"),)

    id: int | None = Field(default=None, primary_key=True)
    osm_id: str = Field(unique=True, index=True)  # mis. "node/123456", supaya impor ulang tidak dobel
    nama: str
    jenis: str  # "tradisional" (amenity=marketplace) atau "modern" (shop=supermarket)
    lat: float = Field(index=True)
    lng: float
    alamat: str | None = None
    wilayah_id: int | None = Field(default=None, foreign_key="wilayah.id")  # wilayah terdekat
    sumber: str = "OpenStreetMap"


class PasarTerdekat(SQLModel):
    id: int
    nama: str
    jenis: str
    lat: float
    lng: float
    alamat: str | None
    jarak_km: float


class PerbandinganPasar(SQLModel):
    tradisional: PasarTerdekat | None  # null kalau tidak ada dalam radius
    modern: PasarTerdekat | None
    lebih_dekat: str | None  # "tradisional" / "modern"; null kalau keduanya tidak ada
    radius_km: float
    atribusi: str = "© OpenStreetMap contributors"


class Resep(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nama: str = Field(unique=True)  # dipakai juga untuk kata kunci pencarian Cookpad
    deskripsi: str
    porsi: int
    waktu_menit: int | None = None


class ResepBahan(SQLModel, table=True):
    # bahan utama resep yang ada di daftar komoditas (bumbu lain tidak dicatat)
    __tablename__ = "resep_bahan"
    __table_args__ = (
        UniqueConstraint("resep_id", "komoditas_id", name="uq_resep_bahan"),
        CheckConstraint("jumlah > 0", name="ck_resep_bahan_jumlah"),
    )

    id: int | None = Field(default=None, primary_key=True)
    resep_id: int = Field(foreign_key="resep.id", index=True)
    komoditas_id: int = Field(foreign_key="komoditas.id")
    jumlah: float  # dalam satuan komoditas, mis. 0.25 (kg)


class BahanResep(SQLModel):
    komoditas: KomoditasRingkas
    jumlah: float  # dalam satuan komoditas (lihat komoditas.satuan)


class ResepHarian(SQLModel):
    id: int
    nama: str
    deskripsi: str
    porsi: int
    waktu_menit: int | None
    tanggal: date  # resep ini untuk tanggal berapa (berganti tiap hari)
    bahan: list[BahanResep]
    link_cookpad: str  # buka di browser; Cookpad tidak punya API publik, jadi tidak di-scraping


class Catatan(SQLModel, table=True):
    # catatan belanja milik satu pengguna (wajib login)
    __table_args__ = (
        CheckConstraint("jenis_pasar IN ('tradisional', 'modern')", name="ck_catatan_jenis_pasar"),
    )

    id: int | None = Field(default=None, primary_key=True)
    pengguna_id: int = Field(foreign_key="pengguna.id", index=True)
    judul: str  # mis. "Belanja Senin"
    wilayah_id: int | None = Field(default=None, foreign_key="wilayah.id")  # untuk harga prediksi; boleh kosong
    jenis_pasar: str = "tradisional"  # pasar tujuan, menentukan harga prediksi yang dipakai
    dibuat_pada: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )
    diubah_pada: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )


class CatatanItem(SQLModel, table=True):
    # satu barang di catatan: dari daftar komoditas ATAU nama ketik sendiri
    __tablename__ = "catatan_item"
    __table_args__ = (
        CheckConstraint(
            "(komoditas_id IS NULL) <> (nama_bebas IS NULL)", name="ck_catatan_item_komoditas_atau_nama"
        ),
        CheckConstraint("jumlah > 0", name="ck_catatan_item_jumlah"),
        CheckConstraint("harga_manual IS NULL OR harga_manual >= 0", name="ck_catatan_item_harga_manual"),
    )

    id: int | None = Field(default=None, primary_key=True)
    catatan_id: int = Field(foreign_key="catatan.id", index=True)
    komoditas_id: int | None = Field(default=None, foreign_key="komoditas.id")
    nama_bebas: str | None = None  # mis. "kerupuk", kalau barangnya tidak ada di daftar komoditas
    jumlah: float  # mis. 0.25 untuk 1/4 kg, 250 untuk 250 gram, 1 untuk 1 kresek
    satuan: str  # bebas: kg, gram, ons, liter, ml, kresek, jumput, ikat, ...
    harga_manual: int | None = None  # total harga yang diisi user sendiri (menimpa harga prediksi)
    sudah_dibeli: bool = False
    dibuat_pada: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )
