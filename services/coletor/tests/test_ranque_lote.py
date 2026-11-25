"""Issue #95: o ranqueamento junta as paradas em poucas chamadas e espera o limitador no worker."""
import asyncio
import json

import httpx
import pytest

from app import ia


def _parada(i: int, n: int = 15) -> dict:
    return {"nome": f"Cidade {i}", "cards": [
        {"id": f"gmaps:ChIJ{i:03d}{j:03d}xxxxxxxxxxxxxxxx", "nome": f"Lugar {i}-{j}", "categoria": "restaurante",
         "tipo": "Churrascaria", "nota": 4.5, "avaliacoes": 300, "descricao": "Comida caseira " * 10,
         "sobre": ["Aceita pets", "Estacionamento"]} for j in range(n)]}


@pytest.fixture
def groq(monkeypatch):
    """Groq simulado: inverte a ordem de cada parada; `falhar` diz quais chamadas dão 500."""
    monkeypatch.setenv("GROQ_API_KEY", "teste")
    ia._limitadores.clear()
    estado = {"pedidos": [], "falhar": set(), "dormidas": []}
    # relógio falso: a espera do limitador (8 mil tokens por minuto) passa na hora
    agora = [0.0]

    async def dormir(s):
        estado["dormidas"].append(s)
        agora[0] += s
    ia._limitadores[ia.MODELO_RAPIDO] = ia.Limitador(relogio=lambda: agora[0], dormir=dormir)

    def h(req):
        corpo = json.loads(req.content)
        estado["pedidos"].append(corpo)
        if len(estado["pedidos"]) in estado["falhar"]:
            return httpx.Response(500)
        dados = json.loads(corpo["messages"][1]["content"])
        saida = {"paradas": [{"parada": p["parada"], "ordem": [c["n"] for c in reversed(p["cards"])]}
                             for p in dados["paradas"]]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(saida)}}],
                                         "usage": {"total_tokens": 500}})

    original = httpx.AsyncClient

    class Cliente(original):
        def __init__(self, *a, **k):
            k["transport"] = httpx.MockTransport(h)
            super().__init__(*a, **k)

    monkeypatch.setattr(ia.httpx, "AsyncClient", Cliente)
    monkeypatch.setattr(ia.uso_ia, "registrar", lambda *a: None)
    return estado


def test_doze_paradas_vao_em_poucas_chamadas_e_nenhuma_cai_no_plano_b(groq):
    paradas = [_parada(i) for i in range(12)]
    originais = [[c["id"] for c in p["cards"]] for p in paradas]
    asyncio.run(ia.ranquear_paradas(paradas, "Gosta de comida caseira."))
    assert len(groq["pedidos"]) <= 6
    # 12 paradas não cabem em 8 mil tokens num minuto: o worker espera a janela, não desiste
    assert groq["dormidas"] and max(groq["dormidas"]) <= ia.ESPERA_LOTE_S
    for p, ids in zip(paradas, originais):
        assert [c["id"] for c in p["cards"]] == list(reversed(ids))
    enviado = json.loads(groq["pedidos"][0]["messages"][1]["content"])
    card = enviado["paradas"][0]["cards"][0]
    assert card["n"] == 0 and "id" not in card  # número no lugar do id: menos tokens
    assert groq["pedidos"][0]["model"] == ia.MODELO_RAPIDO


def test_lotes_respeitam_o_teto_de_tokens():
    topos = [_parada(i)["cards"] for i in range(12)]
    lotes = ia._lotes(topos)
    assert sorted(i for l in lotes for i in l) == list(range(12))
    for l in lotes:
        tokens = sum(ia.estimar_tokens(json.dumps(ia._parada_do_lote(i, topos[i]), ensure_ascii=False)) for i in l)
        assert len(l) == 1 or tokens <= ia.LOTE_TOKENS


def test_lote_que_falha_fica_na_ordem_estatistica_e_o_resto_segue(groq):
    groq["falhar"] = {1}
    paradas = [_parada(i) for i in range(12)]
    originais = [[c["id"] for c in p["cards"]] for p in paradas]
    asyncio.run(ia.ranquear_paradas(paradas, "Gosta de comida caseira."))
    primeiro_lote = ia._lotes([_parada(i)["cards"] for i in range(12)])[0]
    for i, (p, ids) in enumerate(zip(paradas, originais)):
        esperado = ids if i in primeiro_lote else list(reversed(ids))
        assert [c["id"] for c in p["cards"]] == esperado


def test_numeros_estranhos_da_ia_sao_ignorados(monkeypatch):
    async def falso(client, **kw):
        return {"paradas": [{"parada": 0, "ordem": [2, 99, 2, -1, 0]}, {"parada": 7, "ordem": [0]},
                            {"parada": 1, "ordem": []}]}
    monkeypatch.setattr(ia, "chamar_json", falso)
    topos = [_parada(0, 3)["cards"], _parada(1, 3)["cards"]]
    r = asyncio.run(ia._ranquear_lote_pela_ia(None, topos, "x"))
    assert [c["id"] for c in r[0]] == [topos[0][2]["id"], topos[0][0]["id"], topos[0][1]["id"]]
    assert r[1] is None  # sem ordem: plano B da parada


def test_worker_espera_o_limitador_em_vez_de_cair_no_plano_b(groq):
    """Limitador cheio por 40 s: no app seria plano B (prazo de 10 s); no worker, espera."""
    agora = [0.0]
    dormidas = []

    async def dormir(s):
        dormidas.append(s)
        agora[0] += s

    lim = ia.Limitador(relogio=lambda: agora[0], dormir=dormir)
    lim._uso.append((-20.0, 8000))  # janela cheia, abre em 40 s
    ia._limitadores[ia.MODELO_RAPIDO] = lim
    paradas = [_parada(0, 5)]
    ids = [c["id"] for c in paradas[0]["cards"]]
    asyncio.run(ia.ranquear_paradas(paradas, "Gosta de comida caseira."))
    assert dormidas == [40.0]
    assert [c["id"] for c in paradas[0]["cards"]] == list(reversed(ids))


def test_espera_longa_demais_ainda_cai_no_plano_b(groq, monkeypatch):
    monkeypatch.setattr(ia, "ESPERA_LOTE_S", 5.0)
    agora = [0.0]

    async def dormir(s):
        agora[0] += s

    lim = ia.Limitador(relogio=lambda: agora[0], dormir=dormir)
    lim._uso.append((-20.0, 8000))
    ia._limitadores[ia.MODELO_RAPIDO] = lim
    paradas = [_parada(0, 5)]
    ids = [c["id"] for c in paradas[0]["cards"]]
    asyncio.run(ia.ranquear_paradas(paradas, "x"))
    assert groq["pedidos"] == [] and [c["id"] for c in paradas[0]["cards"]] == ids
