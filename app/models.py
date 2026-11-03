from sqlmodel import Field, SQLModel


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
