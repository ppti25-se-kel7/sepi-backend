"""Format error yang seragam untuk semua endpoint.

Setiap error dikirim dengan bentuk yang sama:
    {"kode": "KOMODITAS_TIDAK_DITEMUKAN", "pesan": "Komoditas tidak ditemukan"}
- `kode`  dibaca Flutter untuk menentukan tindakan (tetap, jangan diubah sembarangan).
- `pesan` ditampilkan ke user (Bahasa Indonesia).
- `detail` hanya ada untuk input tidak valid (422): field mana yang salah.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlmodel import SQLModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorDetail(SQLModel):
    field: str
    pesan: str


class ErrorResponse(SQLModel):
    kode: str
    pesan: str
    detail: list[ErrorDetail] | None = None


class AppError(Exception):
    """Error buatan kita: status HTTP + kode (untuk Flutter) + pesan (untuk user)."""

    def __init__(self, status_code: int, kode: str, pesan: str):
        self.status_code = status_code
        self.kode = kode
        self.pesan = pesan


def respons_error(status_code: int, kode: str, pesan: str, detail: list[ErrorDetail] | None = None):
    isi = ErrorResponse(kode=kode, pesan=pesan, detail=detail)
    return JSONResponse(status_code=status_code, content=isi.model_dump(exclude_none=True))


def terjemahkan_pesan_validasi(error: dict) -> str:
    """Ubah pesan validasi bawaan (bahasa Inggris) jadi Bahasa Indonesia untuk kasus yang umum."""
    batas = error.get("ctx", {})
    terjemahan = {
        "missing": "wajib diisi",
        "less_than_equal": f"harus ≤ {batas.get('le', 0):g}",  # :g → 90.0 ditulis 90
        "greater_than_equal": f"harus ≥ {batas.get('ge', 0):g}",
        "float_parsing": "harus berupa angka",
        "int_parsing": "harus berupa bilangan bulat",
        "greater_than": f"harus > {batas.get('gt', 0):g}",
        "string_too_short": "wajib diisi",
        "string_too_long": f"maksimal {batas.get('max_length', 0)} karakter",
        "literal_error": f"harus salah satu dari: {batas.get('expected', '')}",
        "value_error": error["msg"].removeprefix("Value error, "),  # pesan dari validator kita sendiri
    }
    return terjemahan.get(error["type"], error["msg"])


async def tangani_app_error(request: Request, exc: AppError):
    return respons_error(exc.status_code, exc.kode, exc.pesan)


async def tangani_input_tidak_valid(request: Request, exc: RequestValidationError):
    # loc terakhir = nama field; untuk validasi seluruh body (mis. "isi komoditas atau nama") isinya "body"
    detail = [
        ErrorDetail(field=str(error["loc"][-1]), pesan=terjemahkan_pesan_validasi(error)) for error in exc.errors()
    ]
    return respons_error(422, "INPUT_TIDAK_VALID", "Input tidak valid", detail)


async def tangani_http_error(request: Request, exc: StarletteHTTPException):
    # error bawaan FastAPI/Starlette, mis. alamat endpoint yang tidak ada
    if exc.status_code == 404:
        return respons_error(404, "TIDAK_DITEMUKAN", "Alamat tidak ditemukan")
    if exc.status_code == 405:
        return respons_error(405, "METODE_TIDAK_DIIZINKAN", "Metode tidak diizinkan untuk alamat ini")
    return respons_error(exc.status_code, "KESALAHAN_HTTP", str(exc.detail))


async def tangani_kesalahan_server(request: Request, exc: Exception):
    # detail error hanya dicatat di log server, tidak dikirim ke user
    logger.exception("Kesalahan tak terduga di %s", request.url.path)
    return respons_error(500, "KESALAHAN_SERVER", "Terjadi kesalahan di server, coba lagi nanti")


def pasang_penanganan_error(app: FastAPI):
    app.add_exception_handler(AppError, tangani_app_error)
    app.add_exception_handler(RequestValidationError, tangani_input_tidak_valid)
    app.add_exception_handler(StarletteHTTPException, tangani_http_error)
    app.add_exception_handler(Exception, tangani_kesalahan_server)
