"""Resumo da Wikipedia no card: o texto sai em português, ou não sai (bug do teste de 25/11)."""
import asyncio

import httpx

from app import osm


def _cliente(tem_pt: bool) -> tuple[httpx.AsyncClient, list[str]]:
    pedidos: list[str] = []

    def responder(req: httpx.Request) -> httpx.Response:
        pedidos.append(str(req.url))
        if "/w/api.php" in req.url.path:
            links = [{"lang": "pt", "title": "Museu do Carnaval"}] if tem_pt else []
            return httpx.Response(200, json={"query": {"pages": [{"title": "x", "langlinks": links}]}})
        texto = "Texto em português." if req.url.host.startswith("pt.") else "Texto en español."
        return httpx.Response(200, json={"thumbnail": {"source": "https://img/foto.jpg"}, "extract": texto})

    return httpx.AsyncClient(transport=httpx.MockTransport(responder)), pedidos


def test_artigo_em_espanhol_sem_versao_em_portugues_fica_so_com_a_foto():
    cliente, _ = _cliente(tem_pt=False)
    foto, texto = asyncio.run(osm.resumo_wikipedia(cliente, "es:Carnaval en Argentina"))
    assert foto == "https://img/foto.jpg" and texto is None


def test_artigo_em_espanhol_com_versao_em_portugues_usa_o_texto_em_portugues():
    cliente, pedidos = _cliente(tem_pt=True)
    foto, texto = asyncio.run(osm.resumo_wikipedia(cliente, "es:Museo del Carnaval"))
    assert texto == "Texto em português."
    assert any("pt.wikipedia.org/api/rest_v1/page/summary/Museu_do_Carnaval" in p for p in pedidos)


def test_artigo_em_portugues_nao_consulta_outras_linguas():
    cliente, pedidos = _cliente(tem_pt=True)
    _, texto = asyncio.run(osm.resumo_wikipedia(cliente, "pt:Mirante"))
    assert texto == "Texto em português." and len(pedidos) == 1
