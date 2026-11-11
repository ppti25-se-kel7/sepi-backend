"""Halaman dokumentasi API untuk tim, dengan login sederhana.

- /docs     → Scalar: daftar endpoint, tombol "Test Request", contoh kode (Dart, JavaScript, curl, ...)
- /swagger  → Swagger UI bawaan FastAPI (cadangan)
- /redoc    → ReDoc (hanya baca)
- /docs/login, /docs/logout → masuk/keluar

Kalau DOCS_PASSWORD di .env kosong, semua halaman di atas terbuka tanpa login (untuk di laptop).
Kalau diisi, harus login dulu; tanda login disimpan di cookie yang ditandatangani (HMAC), berlaku 8 jam.
Login ini khusus tim pengembang, TERPISAH dari login Firebase milik user aplikasi.
"""

import asyncio
import hashlib
import hmac
import html
import time
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from scalar_fastapi import AgentScalarConfig, get_scalar_api_reference

from app.config import settings
from app.errors import respons_error

NAMA_COOKIE = "sepi_docs"
LAMA_LOGIN_DETIK = 8 * 60 * 60


def login_aktif() -> bool:
    return bool(settings.docs_password)


def tanda_tangan(berlaku_sampai: int) -> str:
    # kunci = username + password: kalau password diganti, semua cookie lama otomatis tidak berlaku
    kunci = f"{settings.docs_username}:{settings.docs_password}".encode()
    return hmac.new(kunci, str(berlaku_sampai).encode(), hashlib.sha256).hexdigest()


def buat_cookie() -> str:
    berlaku_sampai = int(time.time()) + LAMA_LOGIN_DETIK
    return f"{berlaku_sampai}.{tanda_tangan(berlaku_sampai)}"


def sudah_login(request: Request) -> bool:
    if not login_aktif():
        return True
    isi = request.cookies.get(NAMA_COOKIE, "")
    berlaku_sampai, _, tanda = isi.partition(".")
    if not berlaku_sampai.isdigit() or int(berlaku_sampai) < time.time():
        return False
    return hmac.compare_digest(tanda, tanda_tangan(int(berlaku_sampai)))  # compare_digest: aman dari timing attack


def cocok(isian: str, benar: str) -> bool:
    return hmac.compare_digest(isian.encode(), benar.encode())


def halaman_login(pesan_error: str = "") -> str:
    error = f'<p class="error">{html.escape(pesan_error)}</p>' if pesan_error else ""
    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Masuk · Dokumentasi SEPI API</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: #0f172a;
         display: flex; min-height: 100vh; background: #fff; }}
  .kiri {{ width: 100%; max-width: 480px; padding: 48px 64px; display: flex; flex-direction: column; }}
  .kanan {{ flex: 1; background: radial-gradient(circle at 20% 90%, #4ade80 0%, transparent 45%),
            radial-gradient(circle at 80% 10%, #bbf7d0 0%, transparent 50%), #dcfce7; }}
  .merek {{ display: flex; align-items: center; gap: 12px; }}
  .logo {{ width: 52px; height: 52px; border-radius: 12px; background: #15803d; display: grid; place-items: center; }}
  .merek b {{ display: block; font-size: 18px; }}
  .merek span {{ color: #64748b; font-size: 15px; }}
  form {{ margin: auto 0; }}
  h1 {{ font-size: 40px; margin: 0 0 8px; }}
  .sub {{ color: #64748b; margin: 0 0 28px; }}
  input {{ width: 100%; padding: 14px 16px; margin-bottom: 16px; font-size: 15px; border: 1px solid #cbd5e1;
           border-radius: 6px; }}
  input:focus {{ outline: none; border-color: #15803d; box-shadow: 0 0 0 3px #bbf7d0; }}
  button {{ padding: 14px 40px; font-size: 16px; font-weight: 600; color: #fff; background: #0f172a; border: 0;
            border-radius: 6px; cursor: pointer; }}
  button:hover {{ background: #15803d; }}
  .error {{ color: #b91c1c; background: #fef2f2; padding: 10px 14px; border-radius: 6px; }}
  .kaki {{ color: #94a3b8; font-size: 14px; }}
  @media (max-width: 800px) {{ .kanan {{ display: none; }} .kiri {{ max-width: none; padding: 32px 16px; }} }}
</style>
</head>
<body>
  <div class="kiri">
    <div class="merek">
      <div class="logo">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><path d="M3 6h18"/>
          <path d="M16 10a4 4 0 0 1-8 0"/>
        </svg>
      </div>
      <div><b>SEPI</b><span>Dokumentasi API</span></div>
    </div>
    <form method="post" action="/docs/login">
      <h1>Masuk</h1>
      <p class="sub">Khusus tim pengembang SEPI.</p>
      {error}
      <input name="username" placeholder="Username" autocomplete="username" required autofocus>
      <input name="password" type="password" placeholder="Password" autocomplete="current-password" required>
      <button type="submit">Masuk</button>
    </form>
    <p class="kaki">Belum masuk</p>
  </div>
  <div class="kanan"></div>
</body>
</html>"""


TOMBOL_KELUAR = """<a href="/docs/logout" style="position:fixed;right:16px;bottom:16px;z-index:9999;padding:8px 14px;
border-radius:6px;background:#0f172a;color:#fff;font:600 13px system-ui,sans-serif;text-decoration:none">Keluar</a>"""


def tambah_tombol_keluar(respons: HTMLResponse) -> HTMLResponse:
    if not login_aktif():
        return respons
    isi = respons.body.decode().replace("</body>", f"{TOMBOL_KELUAR}</body>")
    return HTMLResponse(isi)


def pasang_dokumentasi(app: FastAPI):
    """Daftarkan halaman dokumentasi. App harus dibuat dengan docs_url/redoc_url/openapi_url = None."""

    def ke_login():
        return RedirectResponse("/docs/login", status_code=303)

    @app.get("/openapi.json", include_in_schema=False)
    def openapi_json(request: Request):
        if not sudah_login(request):
            return respons_error(401, "DOKUMENTASI_BELUM_LOGIN", "Masuk dulu untuk melihat dokumentasi API")
        return JSONResponse(app.openapi())

    @app.get("/docs", include_in_schema=False)
    def scalar(request: Request):
        if not sudah_login(request):
            return ke_login()
        halaman = get_scalar_api_reference(
            openapi_url="/openapi.json",
            title=f"{app.title} · Dokumentasi",
            telemetry=False,  # jangan kirim data pemakaian ke Scalar
            agent=AgentScalarConfig(disabled=True),  # matikan fitur AI bawaan Scalar
            persist_auth=True,  # token login yang diisi di "Test Request" tidak hilang saat halaman di-refresh
            show_developer_tools="never",  # sembunyikan bar promosi Scalar (Deploy, Generate SDK, ...)
            servers=[{"url": str(request.base_url).rstrip("/"), "description": "Server ini"}],  # alamat lengkap di contoh kode
            overrides={"defaultHttpClient": {"targetKey": "dart", "clientKey": "http"}},  # contoh kode Flutter
        )
        return tambah_tombol_keluar(halaman)

    @app.get("/swagger", include_in_schema=False)
    def swagger(request: Request):
        if not sudah_login(request):
            return ke_login()
        return tambah_tombol_keluar(get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} · Swagger"))

    @app.get("/redoc", include_in_schema=False)
    def redoc(request: Request):
        if not sudah_login(request):
            return ke_login()
        return tambah_tombol_keluar(get_redoc_html(openapi_url="/openapi.json", title=f"{app.title} · ReDoc"))

    @app.get("/docs/login", include_in_schema=False)
    def form_login(request: Request):
        if sudah_login(request):
            return RedirectResponse("/docs", status_code=303)
        return HTMLResponse(halaman_login())

    @app.post("/docs/login", include_in_schema=False)
    async def proses_login(request: Request):
        # isi form dibaca manual supaya tidak perlu library tambahan (python-multipart)
        isian = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
        if login_aktif() and cocok(isian.get("username", ""), settings.docs_username) and cocok(
            isian.get("password", ""), settings.docs_password
        ):
            respons = RedirectResponse("/docs", status_code=303)
            respons.set_cookie(
                NAMA_COOKIE,
                buat_cookie(),
                max_age=LAMA_LOGIN_DETIK,
                httponly=True,  # tidak bisa dibaca JavaScript
                samesite="lax",
                secure=request.url.scheme == "https",
            )
            return respons
        await asyncio.sleep(1)  # perlambat tebak-tebakan password
        return HTMLResponse(halaman_login("Username atau password salah"), status_code=401)

    @app.get("/docs/logout", include_in_schema=False)
    def logout():
        respons = RedirectResponse("/docs/login", status_code=303)
        respons.delete_cookie(NAMA_COOKIE)
        return respons
