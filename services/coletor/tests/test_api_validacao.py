"""Issue #35: validar cards na API e não vazar erro interno em /jobs/{id}."""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app import coletor, fila, geo, gmaps, worker
from app.main import app
from conftest import criar_pessoa


@pytest.fixture
def api(pg):
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app, headers=cab)
    cli.uid = uid
    return cli


# --- Card com id obrigatório ---------------------------------------------------

@pytest.mark.parametrize("rota,corpo", [
    ("/cards/ranquear", {"cards": [{"nome": "sem id"}], "resumo": "x"}),
    ("/roteiro", {"cards": [{"nome": "sem id", "km_na_rota": 1}]}),
    ("/swipe", {"card": {"nome": "sem id"}, "gostou": True}),
    ("/swipe", {"card": {"id": ""}, "gostou": True}),
])
def test_card_sem_id_da_422(api, rota, corpo):
    assert api.post(rota, json=corpo).status_code == 422


@pytest.mark.parametrize("card", [
    {"id": "osm:node/1", "lat": 91, "lon": 0},
    {"id": "osm:node/1", "lat": 0, "lon": -181},
    {"id": "osm:node/1", "km_na_rota": "NaN"},
])
def test_coordenada_fora_do_mapa_ou_nan_da_422(api, card):
    assert api.post("/roteiro", json={"cards": [card]}).status_code == 422


def test_card_valido_mantem_os_campos_extras(api):
    card = {"id": "osm:node/1", "nome": "Mirante", "categoria": "turismo", "lat": -29.7, "lon": -55.8,
            "sobre": ["Aceita pets"], "km_na_rota": 10.5}
    assert api.post("/swipe", json={"card": card, "gostou": True}).status_code == 200
    assert api.post("/roteiro", json={"cards": [card]}).json()["itens"] == [card]


# --- Erro amigável em /jobs/{id} -----------------------------------------------

def _rodar_job_que_quebra(api, monkeypatch, erro):
    async def quebra(**kw):
        raise erro
    monkeypatch.setattr(worker.coletor, "planejar_viagem", quebra)
    jid = fila.criar("viagem", {"origem": "A", "destino": "B"}, usuario=api.uid)
    asyncio.run(worker.rodar_uma_vez())
    return api.get(f"/jobs/{jid}").json()


def test_cidade_nao_encontrada_tem_mensagem_amigavel(api, monkeypatch):
    j = _rodar_job_que_quebra(api, monkeypatch, geo.LugarNaoEncontrado("Cidadezinha, XX"))
    assert j["status"] == "falhou"
    assert j["erro"] == "Não achamos Cidadezinha, XX. Confira o nome da cidade e a UF."


def test_sem_rota_tem_mensagem_amigavel_e_neutra(api, monkeypatch):
    j = _rodar_job_que_quebra(api, monkeypatch, geo.RotaNaoEncontrada("NoRoute"))
    assert j["erro"] == "Não achamos uma rota entre essas cidades."  # vale para moto e bicicleta


@pytest.mark.parametrize("erro", [
    httpx.ConnectError("[Errno 111] Connection refused: http://osrm.interno:5000/route"),
    RuntimeError("Overpass indisponível em http://10.0.0.5/api/interpreter"),
    KeyError("routes"),
    gmaps.GosomIndisponivel("Não consegui falar com o gosom em http://gmaps:8080"),
])
def test_erro_desconhecido_nao_vaza_url_nem_host(api, monkeypatch, erro):
    j = _rodar_job_que_quebra(api, monkeypatch, erro)
    assert j["status"] == "falhou"
    for proibido in ("http", "://", "10.0.0.5", "osrm.interno", "gmaps:8080", "Errno", "routes"):
        assert proibido not in j["erro"]
    assert j["erro"]  # tem alguma mensagem para a pessoa


def test_erro_completo_vai_para_o_log(api, monkeypatch, caplog):
    _rodar_job_que_quebra(api, monkeypatch, RuntimeError("detalhe interno http://10.0.0.5"))
    assert "detalhe interno http://10.0.0.5" in caplog.text


def test_aviso_do_google_fora_nao_vaza_endereco_do_gosom(monkeypatch):
    async def fora(client, consultas, **kw):
        raise gmaps.GosomIndisponivel("Não consegui falar com o gosom em http://gmaps:8080")

    async def sem_pois(client, centro, raio, categorias):
        return []
    monkeypatch.setattr(coletor.gmaps, "buscar_lote", fora)
    monkeypatch.setattr(coletor.osm, "pois", sem_pois)
    paradas = [{"nome": "Alegrete", "uf": "RS", "lat": -29.78, "lon": -55.79, "raio_km": 8}]

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as c:
            await coletor.montar_cards(c, paradas, ["turismo"], 3, True, False)
            return paradas
    r = asyncio.run(go())
    assert r[0]["avisos"] and all("http" not in a and "gmaps:8080" not in a for a in r[0]["avisos"])
