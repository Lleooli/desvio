"""Testes sem internet: as APIs externas são simuladas com httpx.MockTransport."""
import asyncio
import csv
import io
import json
from urllib.parse import parse_qs

import httpx
import pytest

from app import coletor, geo, gmaps, instagram, osm, preferencias, roteiro

# Rota reta simulada: de (-29.78,-55.79) subindo ~1.000 km para o norte
ROTA = [(-29.78 + i * 0.09, -55.79 + i * 0.02) for i in range(101)]


def test_amostrar_e_km():
    acc = geo.acumuladas(ROTA)
    pts = geo.amostrar(ROTA, 200)
    assert len(pts) == int(acc[-1] // 200)
    assert all(abs(geo.km_na_rota(ROTA, acc, p) - km) < 12 for km, p in pts)


def test_instagram_regex():
    assert instagram.handle_de_texto("https://www.instagram.com/pizzaria_x/") == "pizzaria_x"
    assert instagram.handle_de_texto("https://instagram.com/p/abc123") is None
    assert instagram.parece_o_mesmo("Churrascaria Gaúcha Lages", "churrascariagauchalages | Instagram")
    assert not instagram.parece_o_mesmo("Restaurante Bom Sabor", "outro lugar qualquer")


def test_osm_categoria_e_tags():
    assert osm.categoria({"amenity": "fuel"}) == "posto"
    assert osm.categoria({"tourism": "viewpoint"}) == "turismo"
    assert osm.categoria({"natural": "waterfall"}) == "natureza"
    assert osm.instagram_das_tags({"contact:instagram": "@meu.bar"}) == "https://instagram.com/meu.bar"
    assert "Special:FilePath" in osm.foto_das_tags({"wikimedia_commons": "File:Foto 1.jpg"})


def test_roteiro_cidade_divide_em_dias():
    cards = [{"id": str(i), "lat": -12.97 + (i % 3) * 0.05, "lon": -38.5 + (i // 3) * 0.05} for i in range(9)]
    dias = roteiro.roteiro_cidade(cards, 3)
    assert [len(d["paradas"]) for d in dias] == [3, 3, 3]
    assert sorted(c["id"] for d in dias for c in d["paradas"]) == sorted(c["id"] for c in cards)
    assert roteiro.ordenar_carro([{"km_na_rota": 5}, {"km_na_rota": 1}])[0]["km_na_rota"] == 1


def test_preferencias(tmp_path, monkeypatch):
    monkeypatch.setattr(preferencias, "DB", str(tmp_path / "t.db"))
    for i, (cat, ok) in enumerate([("restaurante", 1), ("restaurante", 1), ("posto", 0), ("posto", 0)]):
        preferencias.registrar("leo", {"id": f"c{i}", "categoria": cat, "nota": 4.5}, bool(ok))
    p = preferencias.perfil("leo")
    assert p["categoria"]["restaurante"]["taxa"] == 1.0 and p["categoria"]["posto"]["taxa"] == 0.0
    ordem = preferencias.pontuar([{"id": "a", "categoria": "posto"}, {"id": "b", "categoria": "restaurante"}], p)
    assert ordem[0]["id"] == "b"
    assert preferencias.ja_vistos("leo") == {"c0", "c1", "c2", "c3"}


# ---------- fluxo completo com serviços simulados ----------

def _csv_gosom(linhas):
    cab = ["input_id", "link", "title", "category", "address", "open_hours", "website", "phone",
           "review_count", "review_rating", "latitude", "longitude", "status", "descriptions",
           "thumbnail", "price_range", "place_id", "images"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cab)
    w.writeheader()
    for l in linhas:
        w.writerow({k: l.get(k, "") for k in cab})
    return buf.getvalue()


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "nominatim" in url and "/search" in url:
        q = request.url.params["q"]
        lat, lon = (ROTA[0] if "Alegrete" in q else ROTA[-1])
        nome = "Alegrete" if "Alegrete" in q else "Destino"
        return httpx.Response(200, json=[{"lat": str(lat), "lon": str(lon), "display_name": q,
                                          "address": {"city": nome, "ISO3166-2-lvl4": "BR-RS"}}])
    if "nominatim" in url and "/reverse" in url:
        return httpx.Response(200, json={"address": {"city": "X", "ISO3166-2-lvl4": "BR-SC"}})
    if "router.project-osrm.org" in url:
        return httpx.Response(200, json={"code": "Ok", "routes": [{"distance": 1_000_000, "duration": 50_000,
                              "geometry": {"coordinates": [[lo, la] for la, lo in ROTA]}}]})
    if "overpass" in url:
        corpo = parse_qs(request.content.decode())["data"][0]
        if "place" in corpo:
            lat = float(corpo.split("around:")[1].split(",")[1])
            lon = float(corpo.split("around:")[1].split(",")[2].split(")")[0])
            return httpx.Response(200, json={"elements": [
                {"type": "node", "id": 1, "lat": lat + 0.01, "lon": lon, "tags": {"name": f"Cidade{lat:.1f}", "population": "50000"}}]})
        lat = float(corpo.split("around:")[1].split(",")[1])
        lon = float(corpo.split("around:")[1].split(",")[2].split(")")[0])
        return httpx.Response(200, json={"elements": [
            {"type": "node", "id": 10, "lat": lat, "lon": lon, "tags": {"name": "Posto Sul", "amenity": "fuel"}},
            {"type": "node", "id": 11, "lat": lat, "lon": lon, "tags": {"name": "Mirante", "tourism": "viewpoint", "wikipedia": "pt:Mirante"}},
            {"type": "way", "id": 12, "center": {"lat": lat, "lon": lon}, "tags": {"name": "Cantina Boa", "amenity": "restaurant", "website": "https://cantina.example"}},
        ]})
    if "wikipedia.org" in url:
        return httpx.Response(200, json={"thumbnail": {"source": "https://img/mirante.jpg"}, "extract": "Um mirante."})
    if "cantina.example" in url:
        return httpx.Response(200, text='<a href="https://www.instagram.com/cantinaboa/">IG</a>')
    if url.endswith("/api/v1/jobs") and request.method == "POST":
        corpo = json.loads(request.content)
        _handler.keywords = corpo["keywords"]
        return httpx.Response(201, json={"id": "job1"})
    if url.endswith("/api/v1/jobs/job1"):
        return httpx.Response(200, json={"ID": "job1", "Status": "ok"})
    if url.endswith("/download"):
        linhas = []
        for kw in _handler.keywords:
            texto, cid = [x.strip() for x in kw.split("#!#")]
            i = int(cid.split("|")[0])
            if cid.endswith("restaurante"):
                linhas.append({"input_id": cid, "title": f"Churrascaria {i}", "review_rating": "4.700000",
                               "review_count": "1500.000000", "latitude": str(ROTA[min((i + 1) * 20, 100)][0]),
                               "longitude": str(ROTA[min((i + 1) * 20, 100)][1]), "website": f"https://instagram.com/churras{i}",
                               "thumbnail": "https://lh5/x.jpg", "place_id": f"P{i}",
                               "images": json.dumps([{"title": "a", "image": "https://lh5/1.jpg"}])})
                linhas.append({"input_id": cid, "title": "Ruim", "review_rating": "3.1", "review_count": "10",
                               "latitude": str(ROTA[0][0]), "longitude": str(ROTA[0][1])})
        return httpx.Response(200, text=_csv_gosom(linhas))
    return httpx.Response(404)


@pytest.fixture
def mock_http(monkeypatch):
    original = httpx.AsyncClient

    class Cliente(original):
        def __init__(self, *a, **k):
            k["transport"] = httpx.MockTransport(_handler)
            super().__init__(*a, **k)

    monkeypatch.setattr(httpx, "AsyncClient", Cliente)
    monkeypatch.setattr(coletor.httpx, "AsyncClient", Cliente)

    async def sem_espera(*_):
        return None

    real_sleep = asyncio.sleep
    monkeypatch.setattr(geo.asyncio, "sleep", lambda s: real_sleep(0))
    monkeypatch.setattr(instagram, "por_busca", lambda *a: sem_espera())
    geo._cache.clear()


def test_fluxo_carro_sem_google(mock_http):
    r = asyncio.run(coletor.planejar_carro("Alegrete, RS", "Destino, BA", 200))
    assert r["rota"]["distancia_km"] == 1000
    nomes = [p["nome"] for p in r["paradas"]]
    assert nomes[-1] == "Destino" and len(nomes) >= 4
    cards = r["paradas"][0]["cards"]
    assert {c["categoria"] for c in cards} == {"turismo", "restaurante", "posto"}
    mirante = next(c for c in cards if c["nome"] == "Mirante")
    assert mirante["foto"] == "https://img/mirante.jpg"
    cantina = next(c for c in cards if c["nome"] == "Cantina Boa")
    assert cantina["instagram"] == "https://instagram.com/cantinaboa" and cantina["instagram_origem"] == "site"
    kms = [p["km_na_rota"] for p in r["paradas"]]
    assert kms == sorted(kms)


def test_fluxo_carro_com_google(mock_http, monkeypatch):
    real_sleep = asyncio.sleep
    monkeypatch.setattr(gmaps.asyncio, "sleep", lambda s: real_sleep(0))
    r = asyncio.run(coletor.planejar_carro("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True))
    assert any("#!#" in k and ", SC #!#" in k for k in _handler.keywords)
    parada = r["paradas"][1]
    rest = [c for c in parada["cards"] if c["categoria"] == "restaurante"]
    assert rest[0]["fonte"] == "google_maps" and rest[0]["nota"] == 4.7 and rest[0]["avaliacoes"] == 1500
    assert rest[0]["instagram"].startswith("https://instagram.com/churras")
    assert all(c["nome"] != "Ruim" for p in r["paradas"] for c in p["cards"])  # nota baixa / longe filtrados
    assert any(c["fonte"] == "openstreetmap" for c in rest)  # completado com OSM


def test_api(mock_http, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import fila, worker
    from app.main import app
    monkeypatch.setattr(preferencias, "DB", str(tmp_path / "api.db"))
    monkeypatch.setattr(fila, "DB", str(tmp_path / "api.db"))
    cli = TestClient(app)
    r = cli.post("/viagem/aviao", json={"cidades": [{"cidade": "Destino, BA", "dias": 2}], "usuario": "leo"})
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    assert cli.get(f"/jobs/{jid}").json()["status"] == "pendente"
    assert asyncio.run(worker.rodar_uma_vez())
    j = cli.get(f"/jobs/{jid}").json()
    assert j["status"] == "pronto", j
    cards = j["resultado"]["paradas"][0]["cards"]
    assert cli.post("/swipe", json={"usuario": "leo", "card": cards[0], "gostou": True}).json()["ok"]
    assert cli.get("/perfil/leo").json()["aceitos"] == 1
    dias = cli.post("/roteiro/cidade", json={"cards": cards, "dias": 2}).json()
    assert len(dias) == 2


def test_api_job_inexistente(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import fila
    from app.main import app
    monkeypatch.setattr(fila, "DB", str(tmp_path / "x.db"))
    assert TestClient(app).get("/jobs/nao-existe").status_code == 404
