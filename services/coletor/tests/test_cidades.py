"""Issue #7: autocompletar de cidade com UF, sem internet."""
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app import cidades
from app.main import app

api = TestClient(app)


def rotulos(q, **kw):
    return [c["rotulo"] for c in cidades.buscar(q, **kw)]


def test_acento_opcional_e_formato_cidade_uf():
    r = cidades.buscar("vitoria da conq")
    assert r[0]["rotulo"] == "Vitória da Conquista, BA"
    assert r[0]["nome"] == "Vitória da Conquista" and r[0]["uf"] == "BA"
    assert r[0]["lat"] == pytest.approx(-14.86, abs=0.05) and r[0]["lon"] == pytest.approx(-40.84, abs=0.05)


def test_vitoria_acha_vitoria_da_conquista():
    assert "Vitória da Conquista, BA" in rotulos("vitoria")


def test_prefixo_vem_antes_de_palavra_no_meio():
    r = rotulos("lag")
    assert r[0].startswith("Lag")  # Lages, Lagoa..., Laguna antes de "Três Lagoas"
    assert len(r) == 8


def test_capital_desempata():
    assert rotulos("salvador")[0] == "Salvador, BA"
    assert rotulos("sao paulo")[0] == "São Paulo, SP"


def test_palavra_do_meio_tambem_acha():
    assert "Vitória da Conquista, BA" in rotulos("conquista")


def test_filtra_por_uf_com_virgula_ou_espaco():
    assert all(r.endswith(", SC") for r in rotulos("lages, sc"))
    assert rotulos("lages sc")[0] == "Lages, SC"
    assert all(r.endswith(", RS") for r in rotulos("santa rs"))


def test_menos_de_3_letras_nao_busca():
    assert cidades.buscar("la") == []
    assert cidades.buscar("  a  ") == []


def test_no_maximo_8():
    assert len(cidades.buscar("santa")) == 8
    assert len(cidades.buscar("santa", limite=3)) == 3


def test_exata_para_geocodificar():
    c = cidades.exata("Vitória da Conquista, BA")
    assert c and c["uf"] == "BA"
    assert cidades.exata("vitoria da conquista, ba")["nome"] == "Vitória da Conquista"
    assert cidades.exata("Lugar Que Não Existe, ZZ") is None
    assert cidades.exata("Alegrete") is None  # sem UF não dá para ter certeza


# --- API -----------------------------------------------------------------------

def test_endpoint_cidades():
    r = api.get("/cidades", params={"q": "alegre"})
    assert r.status_code == 200
    assert {"nome", "uf", "rotulo", "lat", "lon"} <= set(r.json()[0])
    assert "Alegrete, RS" in [c["rotulo"] for c in r.json()]


def test_endpoint_exige_3_letras():
    assert api.get("/cidades", params={"q": "ab"}).status_code == 422


def test_responde_rapido_sem_internet(monkeypatch):
    def proibido(*a, **k):
        raise AssertionError("não pode chamar a internet")
    monkeypatch.setattr(httpx.AsyncClient, "send", proibido)
    monkeypatch.setattr(httpx.Client, "send", proibido)
    cidades.buscar("aquecimento")  # carrega a lista uma vez
    inicio = time.perf_counter()
    for q in ("lag", "lage", "lages", "sao j", "sao jo", "sao jos", "vitoria d", "bento g", "foz do", "rio gr"):
        cidades.buscar(q)
    assert (time.perf_counter() - inicio) / 10 < 0.3


def test_geocodificar_usa_a_lista_local_sem_nominatim():
    import asyncio
    from app import geo

    def h(req):
        raise AssertionError("não devia chamar o Nominatim")

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
            return await geo.geocodificar(c, "Alegrete, RS")
    r = asyncio.run(go())
    assert r["nome"] == "Alegrete" and r["uf"] == "RS"
