from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pengaturan aplikasi, dibaca dari file .env atau environment variable."""

    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    # alamat website (Flutter web) yang boleh memanggil API ini, dipisah koma.
    # localhost (port berapa pun) selalu diizinkan untuk pengembangan, tidak perlu ditulis di sini.
    cors_origins: str = ""

    @property
    def daftar_cors_origins(self) -> list[str]:
        return [alamat.strip() for alamat in self.cors_origins.split(",") if alamat.strip()]


settings = Settings()
