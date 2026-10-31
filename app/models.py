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
