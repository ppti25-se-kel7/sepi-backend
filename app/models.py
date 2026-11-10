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
    kode: str = Field(unique=True, index=True)  # kode wilayah Kemendagri, mis. "31.71"
    nama: str  # mis. "Kota Jakarta Selatan"
    provinsi: str  # mis. "DKI Jakarta"
    lat: float  # titik tengah wilayah (lintang)
    lng: float  # titik tengah wilayah (bujur)


class Wilayah(WilayahBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class WilayahPublic(WilayahBase):
    id: int


class WilayahTerdekat(WilayahPublic):
    jarak_km: float  # jarak garis lurus dari lokasi user ke titik tengah wilayah


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
