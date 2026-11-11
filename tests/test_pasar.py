import pytest
from sqlmodel import select

from app.models import Pasar, Wilayah
from scripts.impor_pasar_osm import simpan_pasar, ubah_elemen_osm

SENTUL = {"lat": -6.5640, "lng": 106.8590}


@pytest.fixture
def data_contoh(session):
    session.add_all(
        [
            # jarak dari Sentul: ±1,1 km, ±2,2 km, ±0,6 km, ±16 km
            Pasar(osm_id="node/1", nama="Pasar Babakan Madang", jenis="tradisional", lat=-6.5540, lng=106.8590),
            Pasar(osm_id="node/2", nama="Pasar Jauh", jenis="tradisional", lat=-6.5440, lng=106.8590),
            Pasar(osm_id="way/3", nama="Supermarket Sentul", jenis="modern", lat=-6.5640, lng=106.8640),
            Pasar(osm_id="node/4", nama="Supermarket Bogor", jenis="modern", lat=-6.7100, lng=106.8590),
        ]
    )
    session.commit()


def test_terdekat_per_jenis_dan_mana_lebih_dekat(client, data_contoh):
    response = client.get("/markets/nearest", params=SENTUL)
    assert response.status_code == 200
    data = response.json()
    assert data["tradisional"]["nama"] == "Pasar Babakan Madang"
    assert data["tradisional"]["jarak_km"] == pytest.approx(1.11, abs=0.01)
    assert data["modern"]["nama"] == "Supermarket Sentul"
    assert data["lebih_dekat"] == "modern"
    assert data["radius_km"] == 10
    assert data["atribusi"] == "© OpenStreetMap contributors"


def test_di_luar_radius_tidak_ikut(client, data_contoh):
    data = client.get("/markets/nearest", params={**SENTUL, "radius_km": 1}).json()
    assert data["tradisional"] is None
    assert data["modern"]["nama"] == "Supermarket Sentul"


def test_tidak_ada_pasar(client):
    data = client.get("/markets/nearest", params=SENTUL).json()
    assert (data["tradisional"], data["modern"], data["lebih_dekat"]) == (None, None, None)


def test_radius_tidak_valid(client):
    response = client.get("/markets/nearest", params={**SENTUL, "radius_km": 100})
    assert response.status_code == 422
    assert response.json()["detail"] == [{"field": "radius_km", "pesan": "harus ≤ 50"}]


@pytest.mark.parametrize(
    "elemen, hasil",
    [
        (
            {"type": "node", "id": 1, "lat": -6.5, "lon": 106.8,
             "tags": {"amenity": "marketplace", "name": "Pasar Citeureup", "addr:street": "Jl. Raya", "addr:city": "Bogor"}},
            {"osm_id": "node/1", "nama": "Pasar Citeureup", "jenis": "tradisional", "lat": -6.5, "lng": 106.8,
             "alamat": "Jl. Raya, Bogor"},
        ),
        (
            {"type": "way", "id": 2, "center": {"lat": -6.6, "lon": 106.9}, "tags": {"shop": "supermarket", "name": "Super"}},
            {"osm_id": "way/2", "nama": "Super", "jenis": "modern", "lat": -6.6, "lng": 106.9, "alamat": None},
        ),
        ({"type": "node", "id": 3, "lat": -6.5, "lon": 106.8, "tags": {"amenity": "marketplace"}}, None),  # tanpa nama
        ({"type": "node", "id": 4, "lat": -6.5, "lon": 106.8, "tags": {"shop": "bakery", "name": "Roti"}}, None),
    ],
)
def test_ubah_elemen_osm(elemen, hasil):
    assert ubah_elemen_osm(elemen) == hasil


def test_simpan_pasar_upsert_dan_wilayah_terdekat(session):
    bogor = Wilayah(kode="32.71", nama="Kota Bogor", provinsi="Jawa Barat", lat=-6.5951, lng=106.7941)
    depok = Wilayah(kode="32.76", nama="Kota Depok", provinsi="Jawa Barat", lat=-6.3942, lng=106.8227)
    session.add_all([bogor, depok])
    session.commit()
    pasar = {"osm_id": "node/1", "nama": "Pasar A", "jenis": "tradisional", "lat": -6.56, "lng": 106.86, "alamat": None}

    assert simpan_pasar(session, [pasar, pasar], [bogor, depok]) == (1, 0)  # dobel di satu impor → satu
    assert simpan_pasar(session, [{**pasar, "nama": "Pasar A Baru"}], [bogor, depok]) == (0, 1)
    tersimpan = session.exec(select(Pasar)).all()
    assert [(p.nama, p.wilayah_id) for p in tersimpan] == [("Pasar A Baru", bogor.id)]
