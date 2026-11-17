"""Servidores próprios de OSRM, Nominatim e Overpass (#37): tudo vem do ambiente, sem internet."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

from app import geo, osm

PASTA_COLETOR = Path(__file__).resolve().parents[1]
VARIAVEIS = ("PV_OSRM_URL", "PV_OSRM_BIKE_URL", "PV_NOMINATIM_URL", "PV_OVERPASS_URL", "PV_NOMINATIM_INTERVALO")
LER_CONFIG = (
    "import json; from app import geo, osm; "
    "print(json.dumps([geo.OSRM, geo.OSRM_BIKE, geo.NOMINATIM, osm.OVERPASS, geo.NOMINATIM_INTERVALO]))"
)


def _config_com(env_extra: dict) -> list:
    """Importa o app num processo novo (as URLs são lidas no import) e devolve a configuração."""
    env = {k: v for k, v in os.environ.items() if k not in VARIAVEIS}
    env.update(env_extra, PV_ENV_FILE="")  # nunca lê o .env de quem roda
    saida = subprocess.run([sys.executable, "-c", LER_CONFIG], cwd=PASTA_COLETOR, env=env,
                           capture_output=True, text=True, check=True)
    return json.loads(saida.stdout.strip().splitlines()[-1])


def test_sem_variaveis_usa_servidores_publicos_e_1_req_por_segundo():
    assert _config_com({}) == [
        "https://router.project-osrm.org",
        "https://routing.openstreetmap.de/routed-bike",
        "https://nominatim.openstreetmap.org",
        "https://overpass-api.de/api/interpreter",
        1.1,
    ]


def test_variaveis_apontam_para_os_servidores_proprios():
    assert _config_com({
        "PV_OSRM_URL": "http://10.0.0.5:5000",
        "PV_OSRM_BIKE_URL": "http://10.0.0.5:5001",
        "PV_NOMINATIM_URL": "http://10.0.0.5:8088",
        "PV_OVERPASS_URL": "http://10.0.0.5:12345/api/interpreter",
        "PV_NOMINATIM_INTERVALO": "0",
    }) == [
        "http://10.0.0.5:5000",
        "http://10.0.0.5:5001",
        "http://10.0.0.5:8088",
        "http://10.0.0.5:12345/api/interpreter",
        0.0,
    ]


def _cliente(urls: list[str]) -> httpx.AsyncClient:
    def responder(req: httpx.Request) -> httpx.Response:
        urls.append(str(req.url))
        if req.url.path.endswith("/search"):
            return httpx.Response(200, json=[{"lat": "-29.78", "lon": "-55.79", "address": {"city": "Alegrete"}}])
        if "/route/v1/" in req.url.path:
            return httpx.Response(200, json={"code": "Ok", "routes": [{
                "distance": 1000.0, "duration": 60.0,
                "geometry": {"coordinates": [[-55.79, -29.78], [-55.78, -29.77]]}}]})
        return httpx.Response(200, json={"elements": []})
    return httpx.AsyncClient(transport=httpx.MockTransport(responder))


def test_chamadas_vao_para_as_urls_configuradas(monkeypatch):
    monkeypatch.setattr(geo, "NOMINATIM", "http://osm.local:8088")
    monkeypatch.setattr(geo, "OSRM", "http://osm.local:5000")
    monkeypatch.setattr(geo, "OSRM_BIKE", "http://osm.local:5001")
    monkeypatch.setattr(osm, "OVERPASS", "http://osm.local:12345/api/interpreter")
    monkeypatch.setattr(geo, "NOMINATIM_INTERVALO", 0)
    geo._cache.clear()
    urls: list[str] = []

    async def rodar():
        async with _cliente(urls) as c:
            await geo.geocodificar(c, "Alegrete, RS")
            await geo.rota(c, (-29.78, -55.79), (-14.86, -40.84), "moto")
            await geo.rota(c, (-29.78, -55.79), (-14.86, -40.84), "bicicleta")
            await osm._overpass(c, "[out:json];node(1);out;")

    asyncio.run(rodar())
    assert urls[0].startswith("http://osm.local:8088/search?")
    assert urls[1].startswith("http://osm.local:5000/route/v1/driving/")  # moto usa o perfil de carro
    assert urls[2].startswith("http://osm.local:5001/route/v1/bike/")
    assert urls[3] == "http://osm.local:12345/api/interpreter"


def _esperas(monkeypatch, intervalo: float) -> list[float]:
    monkeypatch.setattr(geo, "NOMINATIM_INTERVALO", intervalo)
    esperas: list[float] = []
    real_sleep = asyncio.sleep

    async def dormir(s):
        esperas.append(s)
        await real_sleep(0)

    monkeypatch.setattr(geo.asyncio, "sleep", dormir)
    geo._cache.clear()

    async def rodar():
        async with _cliente([]) as c:
            await geo.geocodificar(c, "Alegrete, RS")
            await geo.geocodificar(c, "Lages, SC")

    asyncio.run(rodar())
    return esperas


def test_nominatim_publico_espera_entre_chamadas(monkeypatch):
    assert _esperas(monkeypatch, 1.1) == [1.1, 1.1]


def test_nominatim_proprio_sem_espera(monkeypatch):
    assert _esperas(monkeypatch, 0) == []


def test_intervalo_do_nominatim_aceita_virgula_e_protege_o_servidor_publico():
    from app import geo
    proprio = "http://localhost:8088"
    assert geo._intervalo_nominatim("1,5", proprio) == 1.5
    assert geo._intervalo_nominatim("abc", proprio) == 1.1
    assert geo._intervalo_nominatim("0", proprio) == 0.0
    assert geo._intervalo_nominatim("0", geo.NOMINATIM_PUBLICO) == 1.0
