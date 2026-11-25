"""Issue #95: a rota entre duas cidades do Brasil não sai do país. Sem internet (OSRM simulado)."""
import asyncio

import httpx

from app import coletor, fronteira, geo

ALEGRETE = (-29.78, -55.79)
CASCAVEL = (-24.96, -53.46)
# Por Misiones e pelo Paraguai (Hohenau), como o OSRM público fez em 24/11
PELO_PARAGUAI = [ALEGRETE, (-28.5, -55.9), (-27.08, -55.65), (-26.0, -55.0), (-25.51, -54.61), CASCAVEL]
# Pelo oeste do RS e de SC, sem sair do Brasil
PELO_BRASIL = [ALEGRETE, (-28.3, -54.3), (-27.1, -52.6), (-26.2, -52.7), CASCAVEL]


def _rota(pontos, duracao):
    return {"distance": 900_000, "duration": duracao,
            "geometry": {"coordinates": [[lo, la] for la, lo in pontos]}}


def _rodar(handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await geo.rota(c, ALEGRETE, CASCAVEL, "carro")
    return asyncio.run(go())


def test_contorno_do_brasil():
    assert fronteira.no_brasil(ALEGRETE) and fronteira.no_brasil((-14.86, -40.84))  # Vitória da Conquista
    assert fronteira.no_brasil((-25.54, -54.58))  # Foz do Iguaçu, colada na fronteira
    assert fronteira.no_brasil((-27.59, -48.55))  # Florianópolis, na ilha
    assert not fronteira.no_brasil((-27.08, -55.65))  # Hohenau, Paraguai
    assert not fronteira.no_brasil((-27.37, -55.90))  # Posadas, Argentina
    assert fronteira.pontos_fora(PELO_PARAGUAI) and not fronteira.pontos_fora(PELO_BRASIL)


def test_rota_pelo_paraguai_perde_para_a_alternativa_no_brasil():
    pedidos = []

    def h(req):
        pedidos.append(req)
        return httpx.Response(200, json={"code": "Ok", "routes": [_rota(PELO_PARAGUAI, 30_000),
                                                                   _rota(PELO_BRASIL, 34_000)]})
    r = _rodar(h)
    assert r["pontos"] == PELO_BRASIL and r["duracao_h"] == 34_000 / 3600
    assert "sai_do_brasil" not in r
    assert len(pedidos) == 1 and pedidos[0].url.params["alternatives"] == "3"


def test_sem_alternativa_no_brasil_passa_por_uma_cidade_brasileira():
    pedidos = []

    def h(req):
        pedidos.append(req)
        coords = req.url.path.split("/")[-1].split(";")
        if len(coords) == 2:
            return httpx.Response(200, json={"code": "Ok", "routes": [_rota(PELO_PARAGUAI, 30_000)]})
        return httpx.Response(200, json={"code": "Ok", "routes": [_rota(PELO_BRASIL, 34_000)]})
    r = _rodar(h)
    assert r["pontos"] == PELO_BRASIL and "sai_do_brasil" not in r
    via = pedidos[1].url.path.split("/")[-1].split(";")
    assert len(via) == 3 and "alternatives" not in pedidos[1].url.params
    lo, la = map(float, via[1].split(","))
    assert fronteira.no_brasil((la, lo), margem_km=0)


def test_rota_que_nao_tem_como_ficar_no_brasil_vem_marcada():
    def h(req):
        return httpx.Response(200, json={"code": "Ok", "routes": [_rota(PELO_PARAGUAI, 30_000)]})
    r = _rodar(h)
    assert r["pontos"] == PELO_PARAGUAI and r["sai_do_brasil"] is True


def test_viagem_que_sai_do_brasil_nao_tenta_corrigir():
    pedidos = []

    def h(req):
        pedidos.append(req)
        return httpx.Response(200, json={"code": "Ok", "routes": [_rota(PELO_PARAGUAI, 30_000)]})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
            return await geo.rota(c, ALEGRETE, (-25.30, -57.63), "carro")  # Assunção
    r = asyncio.run(go())
    assert len(pedidos) == 1 and "sai_do_brasil" not in r


def test_parada_fora_do_brasil_e_descartada(monkeypatch):
    """Rota colada na fronteira: a cidade maior perto da estrada pode ser do país vizinho."""
    async def rota(client, o, d, veiculo):
        return {"distancia_km": 900, "duracao_h": 10, "pontos": PELO_BRASIL, "sai_do_brasil": True}

    async def geocodificar(client, lugar):
        p = ALEGRETE if "Alegrete" in lugar else CASCAVEL
        return {"nome": lugar.split(",")[0], "uf": "RS", "lat": p[0], "lon": p[1], "exibicao": lugar}

    cidades = iter([{"nome": "Posadas", "lat": -27.37, "lon": -55.90},  # longe: o contorno já tira
                    {"nome": "Ciudad del Este", "lat": -25.51, "lon": -54.61},  # colada: o Nominatim diz "py"
                    {"nome": "Chapecó", "lat": -27.10, "lon": -52.61}] + [None] * 20)

    async def cidade_proxima(client, ponto):
        return next(cidades)

    async def cidade_uf_pais(client, ponto):
        return ("Ciudad del Este", None, "py") if ponto[0] == -25.51 else ("Chapecó", "SC", "br")

    async def montar_cards(client, paradas, *a, **k):
        for p in paradas:
            p["cards"] = []
        return paradas

    monkeypatch.setattr(geo, "rota", rota)
    monkeypatch.setattr(geo, "geocodificar", geocodificar)
    monkeypatch.setattr(coletor, "_cidade_proxima_com_cache", cidade_proxima)
    monkeypatch.setattr(geo, "cidade_uf_pais", cidade_uf_pais)
    monkeypatch.setattr(coletor, "montar_cards", montar_cards)
    r = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Cascavel, PR", 100))
    assert [p["nome"] for p in r["paradas"]] == ["Chapecó", "Cascavel"]
