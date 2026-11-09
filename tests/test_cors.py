from app.config import Settings


def test_flutter_web_localhost_diizinkan(client):
    response = client.get("/komoditas", headers={"Origin": "http://localhost:53421"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:53421"


def test_preflight_dengan_authorization(client):
    # browser bertanya dulu (preflight) sebelum mengirim request dengan header Authorization
    response = client.options(
        "/komoditas",
        headers={
            "Origin": "http://127.0.0.1:8080",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8080"


def test_website_lain_tidak_diizinkan(client):
    response = client.get("/komoditas", headers={"Origin": "https://situs-asing.com"})
    assert response.status_code == 200  # data tetap dikirim, tapi browser akan memblokirnya
    assert "access-control-allow-origin" not in response.headers


def test_daftar_cors_origins_dari_env():
    settings = Settings(database_url="sqlite://", cors_origins=" https://a.com, ,https://b.com ")
    assert settings.daftar_cors_origins == ["https://a.com", "https://b.com"]
