"""Issue #93: cidades já coletadas são reaproveitadas entre viagens e pessoas, sem coleta nem IA."""
import asyncio
import time

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import coletor, geo, gmaps, ia, instagram, preferencias, worker
from app.main import app
from conftest import criar_pessoa
from test_offline import _contar_chamadas, mock_http  # noqa: F401 (fixture)

PEDIDO = {"origem": "Alegrete, RS", "destino": "Destino, BA", "veiculo": "carro", "intervalo_km": 200}


def _sem_rede() -> httpx.AsyncClient:
    def recusa(request):
        raise AssertionError(f"não devia ir à rede: {request.url}")
    return httpx.AsyncClient(transport=httpx.MockTransport(recusa))


def _restaurante(i: int, **extra) -> dict:
    return {"id": f"osm:node/{i}", "nome": f"Cantina {i}", "cidade": "Lages", "categoria": "restaurante", **extra}


def test_instagram_fica_no_cache_por_lugar(pg, monkeypatch):
    buscas = []

    async def busca(nome, cidade):
        buscas.append(nome)
        return "cantina1" if nome == "Cantina 1" else None

    monkeypatch.setattr(instagram, "por_busca", busca)
    monkeypatch.setattr(instagram.asyncio, "sleep", lambda s: _nada())

    async def rodar():
        cards = [_restaurante(1), _restaurante(2)]
        async with _sem_rede() as client:
            await instagram.completar(client, cards)
        return cards

    primeira = asyncio.run(rodar())
    assert buscas == ["Cantina 1", "Cantina 2"]
    assert primeira[0]["instagram"] == "https://instagram.com/cantina1" and primeira[0]["instagram_origem"] == "busca"

    segunda = asyncio.run(rodar())
    assert buscas == ["Cantina 1", "Cantina 2"]  # nada de busca nova
    assert segunda[0]["instagram"] == "https://instagram.com/cantina1" and segunda[0]["instagram_origem"] == "busca"
    assert "instagram" not in segunda[1]
    with psycopg.connect(pg) as con:
        chaves = {r[0] for r in con.execute("select chave from cache where chave like 'instagram%'")}
    assert chaves == {"instagram|osm:node/1", "instagram-vazio|osm:node/2"}


def test_sem_instagram_vence_em_7_dias_e_o_achado_em_30(pg, monkeypatch):
    buscas = []

    async def busca(nome, cidade):
        buscas.append(nome)
        return None

    monkeypatch.setattr(instagram, "por_busca", busca)
    monkeypatch.setattr(instagram.asyncio, "sleep", lambda s: _nada())

    def rodar():
        async def _r():
            async with _sem_rede() as client:
                await instagram.completar(client, [_restaurante(2)])
        asyncio.run(_r())

    rodar()
    with psycopg.connect(pg) as con:
        con.execute("update cache set guardado_em = now() - interval '6 days'")
    rodar()
    assert buscas == ["Cantina 2"]
    with psycopg.connect(pg) as con:
        con.execute("update cache set guardado_em = now() - interval '8 days'")
    rodar()
    assert buscas == ["Cantina 2", "Cantina 2"]


def test_sem_a_busca_nao_guarda_sem_instagram(pg, monkeypatch):
    async def rodar():
        async with _sem_rede() as client:
            await instagram.completar(client, [_restaurante(3)], usar_busca=False)
    asyncio.run(rodar())
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from cache where chave like 'instagram%'").fetchone()[0] == 0


async def _nada():
    return None


# ---------- cidades já feitas (parada_cidade) ----------

@pytest.fixture(autouse=True)
def _dois_por_categoria(monkeypatch):
    """O Overpass do mock acha um lugar por categoria; com dois, a categoria vai à IA."""
    from app import osm
    original = osm.pois

    async def dobrado(*a, **k):
        res = await original(*a, **k)
        return res + [{**x, "osm_id": x["osm_id"] + "0", "nome": x["nome"] + " Dois"} for x in res]
    monkeypatch.setattr(osm, "pois", dobrado)


def _coletas(monkeypatch) -> list[dict]:
    """Conta as vezes que o worker chamou a coleta."""
    chamadas, original = [], coletor.planejar_viagem

    async def contando(**kw):
        chamadas.append(kw)
        return await original(**kw)
    monkeypatch.setattr(worker.coletor, "planejar_viagem", contando)
    return chamadas


def _groq_falso(monkeypatch) -> list[dict]:
    """chamar_json sem rede: o ranqueamento em lote inverte a ordem de cada cidade."""
    pedidos = []

    async def falso(client, *, nome, dados, **kw):
        pedidos.append({"nome": nome, **dados})
        return {"paradas": [{"parada": p["parada"], "ordem": [c["n"] for c in reversed(p["cards"])]}
                            for p in dados["paradas"]]}
    monkeypatch.setattr(ia, "chamar_json", falso)
    return pedidos


def _viajar(cli, cab, **mudanca) -> dict:
    r = cli.post("/viagem", json={**PEDIDO, **mudanca}, headers=cab)
    assert r.status_code == 202, r.text
    assert asyncio.run(worker.rodar_uma_vez()) is True
    j = cli.get(f"/jobs/{r.json()['job_id']}", headers=cab).json()
    assert j["status"] == "pronto", j
    return {**r.json(), "resultado": j["resultado"]}


def _zerar(cont: dict) -> None:
    geo._cache.clear()  # outro processo do worker: só o banco sobrevive
    for k in cont:
        cont[k] = 0


def _ids(r: dict) -> list[list[str]]:
    return [[c["id"] for c in p["cards"]] for p in r["resultado"]["paradas"]]


def test_outra_origem_pelas_mesmas_cidades_nao_coleta_nem_chama_o_groq(mock_http, monkeypatch, pg):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    groq = _groq_falso(monkeypatch)
    cont = _contar_chamadas(monkeypatch)
    primeira = _viajar(cli, cab)
    assert cont["overpass"] > 0 and len(groq) >= 1
    assert all(p["ranqueada"] for p in primeira["resultado"]["paradas"])
    with psycopg.connect(pg) as con:
        linhas = con.execute("select cidade, categoria, ordem_ia from parada_cidade").fetchall()
    assert len({l[0] for l in linhas}) == len(primeira["resultado"]["paradas"])
    assert len(linhas) == 3 * len(primeira["resultado"]["paradas"])  # uma linha por categoria
    assert all(l[2] is not None for l in linhas)
    assert any(l[0].startswith("nome:cidade") for l in linhas)  # cidade fora da lista do IBGE

    _zerar(cont)
    groq.clear()
    inicio = time.perf_counter()
    segunda = _viajar(cli, cab, origem="Uruguaiana, RS")  # outra origem, o mesmo trecho
    assert time.perf_counter() - inicio < 2
    assert cont["overpass"] == 0 and cont["gosom"] == 0 and cont["nominatim"] == 0
    assert groq == []  # zero chamadas ao Groq no ranqueamento
    assert [p["nome"] for p in segunda["resultado"]["paradas"]] == [p["nome"] for p in primeira["resultado"]["paradas"]]
    # cada pessoa recebe a ordem genérica com o gosto dela por cima (aqui, ninguém avaliou nada)
    assert _ids(segunda) == _ids(primeira)


def test_gosto_diferente_nao_chama_a_ia_de_novo(mock_http, monkeypatch, pg):
    uid_a, cab_a = criar_pessoa(pg)
    uid_b, cab_b = criar_pessoa(pg)
    preferencias.guardar_triagem(uid_a, None, [{"pergunta": "P", "resposta": "R"}], "Gosta de mirantes.", pulou=False)
    preferencias.guardar_triagem(uid_b, None, [{"pergunta": "P", "resposta": "S"}], "Só quer posto.", pulou=False)
    cli = TestClient(app)
    groq = _groq_falso(monkeypatch)
    a = _viajar(cli, cab_a)
    assert groq and all(p["gosto"] == ia.GOSTO_GENERICO for p in groq)  # o gosto de ninguém vai para a IA
    card = a["resultado"]["paradas"][0]["cards"][0]
    assert cli.post("/swipe", json={"card": card, "tipo": "passo"}, headers=cab_b).status_code == 200
    groq.clear()
    b = _viajar(cli, cab_b)
    assert groq == []
    assert card["id"] not in _ids(b)[0]  # o gosto (e o que B já avaliou) entra sem IA
    assert _ids(b)[0] == [i for i in _ids(a)[0] if i != card["id"]]


def _pois_contando(monkeypatch) -> list[list[str]]:
    """Anota as categorias pedidas ao Overpass; hospedagem volta com dois hotéis."""
    from app import osm
    pedidas, original = [], osm.pois

    async def contando(client, centro, raio_km, categorias, *a, **k):
        pedidas.append(list(categorias))
        res = await original(client, centro, raio_km, [c for c in categorias if c != "hospedagem"], *a, **k) \
            if set(categorias) - {"hospedagem"} else []
        if "hospedagem" in categorias:
            lat, lon = centro
            res += [{"osm_id": f"node/9{n}{abs(round(lat * 10))}", "nome": f"Hotel {n}", "categoria": "hospedagem",
                     "lat": lat, "lon": lon, "tags": {"name": f"Hotel {n}", "tourism": "hotel"}} for n in (1, 2)]
        return res
    monkeypatch.setattr(osm, "pois", contando)
    return pedidas


def test_cidade_feita_com_mais_categorias_atende_viagem_com_menos(mock_http, monkeypatch, pg):
    """(e) cidade feita com turismo, restaurante e posto atende turismo e restaurante, sem coleta nem IA."""
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    groq = _groq_falso(monkeypatch)
    cont = _contar_chamadas(monkeypatch)
    pedidas = _pois_contando(monkeypatch)
    primeira = _viajar(cli, cab, categorias=["turismo", "restaurante", "posto"])
    _zerar(cont)
    groq.clear()
    pedidas.clear()
    segunda = _viajar(cli, cab, categorias=["turismo", "restaurante"])
    assert pedidas == [] and cont["overpass"] == 0 and groq == []
    for p1, p2 in zip(primeira["resultado"]["paradas"], segunda["resultado"]["paradas"]):
        assert p1["nome"] == p2["nome"]
        cats = [c["categoria"] for c in p2["cards"]]
        assert set(cats) <= {"turismo", "restaurante"} and cats[0] == "turismo"
        assert [c["id"] for c in p2["cards"]] == [c["id"] for c in p1["cards"] if c["categoria"] != "posto"]


def test_categoria_nova_na_mesma_cidade_coleta_e_ranqueia_so_ela(mock_http, monkeypatch, pg):
    """(f) viagem com turismo e hospedagem na cidade feita coleta e ranqueia só a hospedagem."""
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    groq = _groq_falso(monkeypatch)
    pedidas = _pois_contando(monkeypatch)
    primeira = _viajar(cli, cab)
    groq.clear()
    pedidas.clear()
    segunda = _viajar(cli, cab, categorias=["turismo", "hospedagem"])
    assert pedidas and all(p == ["hospedagem"] for p in pedidas)  # o turismo saiu da tabela
    cards_na_ia = [c for pedido in groq for p in pedido["paradas"] for c in p["cards"]]
    assert cards_na_ia and all(c["nome"].startswith("Hotel") for c in cards_na_ia)
    for p1, p2 in zip(primeira["resultado"]["paradas"], segunda["resultado"]["paradas"]):
        cats = [c["categoria"] for c in p2["cards"]]
        assert cats[:2] == ["turismo", "hospedagem"]  # intercaladas, na ordem pedida
        assert [c["id"] for c in p2["cards"] if c["categoria"] == "turismo"] == \
               [c["id"] for c in p1["cards"] if c["categoria"] == "turismo"]
        assert sorted(c["nome"] for c in p2["cards"] if c["categoria"] == "hospedagem") == ["Hotel 1", "Hotel 2"]
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from parada_cidade where categoria = 'hospedagem'").fetchone()[0] \
            == len(segunda["resultado"]["paradas"])


def test_cidade_vencida_ou_incompleta_e_coletada_de_novo(mock_http, monkeypatch, pg):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    groq = _groq_falso(monkeypatch)
    cont = _contar_chamadas(monkeypatch)
    _viajar(cli, cab)
    with psycopg.connect(pg) as con:
        # 31 dias depois, venceram a cidade e o cache dos lugares dela
        con.execute("update parada_cidade set atualizado_em = now() - interval '31 days' "
                    "where cidade like 'nome:cidade%%'")
        con.execute("update cache set guardado_em = now() - interval '31 days' where chave like 'osm|%%'")
    _zerar(cont)
    groq.clear()
    _viajar(cli, cab)
    assert cont["overpass"] > 0 and groq  # as vencidas voltam à coleta e à IA
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from parada_cidade "
                           "where atualizado_em < now() - interval '1 day'").fetchone()[0] == 0

    with psycopg.connect(pg) as con:  # incompleta (Google vazio) vale só 1 dia
        con.execute("update parada_cidade set completa = false, atualizado_em = now() - interval '2 days'")
    groq.clear()
    _viajar(cli, cab)
    assert groq  # voltou à coleta (os lugares saem do cache de 30 dias) e à IA
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from parada_cidade "
                           "where atualizado_em < now() - interval '1 day'").fetchone()[0] == 0


def test_forcar_recoleta_e_atualiza_a_cidade(mock_http, monkeypatch, pg):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    groq = _groq_falso(monkeypatch)
    cont = _contar_chamadas(monkeypatch)
    coletas = _coletas(monkeypatch)
    _viajar(cli, cab)
    with psycopg.connect(pg) as con:
        con.execute("update parada_cidade set atualizado_em = now() - interval '10 days'")
    _zerar(cont)
    groq.clear()
    _viajar(cli, cab, forcar=True)
    assert coletas[-1]["forcar"] is True
    assert cont["overpass"] > 0 and groq  # nada sai de parada_cidade nem do cache de lugares
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from parada_cidade "
                           "where atualizado_em < now() - interval '1 day'").fetchone()[0] == 0
    _zerar(cont)
    _viajar(cli, cab)
    assert cont["overpass"] == 0


def _cidade_feita(km_alvo: float, nome: str) -> None:
    """Grava em parada_cidade uma cidade no ponto da ROTA mais perto de `km_alvo`."""
    from app import parada_cidade
    from test_offline import ROTA
    acc = geo.acumuladas(ROTA)
    i = min(range(len(ROTA)), key=lambda k: abs(acc[k] - km_alvo))
    lat, lon = ROTA[i]
    card = {"id": f"osm:node/{nome}", "nome": f"Lugar de {nome}", "categoria": "turismo", "lat": lat, "lon": lon}
    parada_cidade.guardar(parada_cidade.id_cidade(nome, "RS"), "turismo",
                          parada_cidade.variante(8, 5, False), {"nome": nome, "uf": "RS", "lat": lat, "lon": lon},
                          [card], [card["id"]], True)


def test_parada_puxa_para_cidade_feita_so_dentro_da_folga(mock_http, monkeypatch, pg):
    """Intervalo de 200 km: folga de 10% (20 km). A 15 km do ponto vale; a 40 km, não."""
    _cidade_feita(215, "Perto")
    _cidade_feita(440, "Longe")
    _groq_falso(monkeypatch)
    r = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200))
    nomes = [p["nome"] for p in r["paradas"]]
    assert "Perto" in nomes and "Longe" not in nomes
    perto = next(p for p in r["paradas"] if p["nome"] == "Perto")
    # o turismo veio da tabela (só tinha ele); restaurante e posto foram coletados
    assert [c["id"] for c in perto["cards"] if c["categoria"] == "turismo"] == ["osm:node/Perto"]
    assert perto["cards"][0]["id"] == "osm:node/Perto"
    assert {c["categoria"] for c in perto["cards"]} == {"turismo", "restaurante", "posto"}
    kms = [p["km_na_rota"] for p in r["paradas"]]
    assert kms == sorted(kms)


def test_folga_configuravel(monkeypatch):
    feitas = [{"nome": "A", "km": 215.0}, {"nome": "B", "km": 240.0}]
    assert coletor._feita_perto(feitas, 200, 200, 1000, set())["nome"] == "A"
    assert coletor._feita_perto([feitas[1]], 200, 200, 1000, set()) is None
    monkeypatch.setattr(coletor, "FOLGA_PARADA", 0.25)
    assert coletor._feita_perto([feitas[1]], 200, 200, 1000, set())["nome"] == "B"
    assert coletor._feita_perto(feitas, 200, 200, 1000, {"a"})["nome"] == "B"  # já é parada
    # dentro da folga, ganha a cidade com mais categorias pedidas, mesmo um pouco mais longe
    monkeypatch.setattr(coletor, "FOLGA_PARADA", 0.1)
    com_mais = [{"nome": "A", "km": 202.0, "n": 1}, {"nome": "B", "km": 215.0, "n": 3}]
    assert coletor._feita_perto(com_mais, 200, 200, 1000, set())["nome"] == "B"


def test_intercala_as_categorias_sem_repetir():
    t = [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}]
    r = [{"id": "r1"}, {"id": "t2"}]
    assert [c["id"] for c in coletor._intercalar([t, r, []])] == ["t1", "r1", "t2", "t3"]


def _linhas(pg) -> list[tuple]:
    with psycopg.connect(pg) as con:
        return con.execute("select cidade, completa, categoria from parada_cidade").fetchall()


def test_google_vazio_fica_incompleto_e_places_ou_google_fora_nao_grava(mock_http, monkeypatch, pg):
    real_sleep = asyncio.sleep
    monkeypatch.setattr(gmaps.asyncio, "sleep", lambda s: real_sleep(0))
    _groq_falso(monkeypatch)
    # o gosom do mock só acha restaurantes: turismo e posto voltam vazios em toda cidade
    asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True))
    assert _linhas(pg) and all(completa == (cat == "restaurante") for _, completa, cat in _linhas(pg))

    with psycopg.connect(pg) as con:
        con.execute("truncate parada_cidade")
    monkeypatch.setenv("PV_GOOGLE_PLACES_KEY", "chave-de-teste")
    asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True))
    assert _linhas(pg) == []  # termos da Places API: nada do Google no banco compartilhado
    monkeypatch.delenv("PV_GOOGLE_PLACES_KEY")

    async def fora(*a, **k):
        raise gmaps.GosomIndisponivel("fora do ar")
    monkeypatch.setattr(gmaps, "buscar_lote", fora)
    asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True, forcar=True))
    assert _linhas(pg) == []


def test_ia_fora_do_ar_grava_sem_ordem_e_tenta_de_novo_depois(mock_http, monkeypatch, pg):
    async def fora(client, **kw):
        raise ia.IAIndisponivel("Groq 429")
    monkeypatch.setattr(ia, "chamar_json", fora)
    r = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200))
    assert not any(p["ranqueada"] for p in r["paradas"])
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from parada_cidade where ordem_ia is null").fetchone()[0] > 0
    groq = _groq_falso(monkeypatch)
    geo._cache.clear()
    r = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200))
    assert groq and all(p["ranqueada"] for p in r["paradas"])
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from parada_cidade where ordem_ia is null").fetchone()[0] == 0


def test_banco_fora_do_ar_nao_derruba_a_coleta(mock_http, monkeypatch):
    from app import banco

    def fora_do_ar(*a, **k):
        raise psycopg.OperationalError("connection refused")
    monkeypatch.setattr(banco, "URL", "postgresql://banco-fora-do-ar")
    monkeypatch.setattr(banco, "conectar", fora_do_ar)
    r = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200))
    assert r["paradas"][0]["cards"]


# ---------- roteiro da IA ----------

def _roteiro_ia(cli, cab, vid, saida="07:00"):
    r = cli.post(f"/viagens/{vid}/roteiro", headers=cab, json={"usar_ia": True, "contexto": {"saida": saida, "dias": 1}})
    assert r.status_code == 200, r.text
    return r.json()


def test_roteiro_da_ia_com_as_mesmas_escolhas_sai_do_cache(pg, monkeypatch):
    from test_viagens import card, criar_e_coletar, resultado
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab, monkeypatch, resultado([card(1), card(2)], [card(3)]))
    for i in (1, 2, 3):
        cli.post("/swipe", json={"card": card(i), "gostou": True}, headers=cab)
    pedidos = []

    async def groq_falso(client, **kw):
        pedidos.append(kw["dados"]["contexto"])
        ids = [l["id"] for l in kw["dados"]["lugares"]]
        return {"ordem": [{"id": i, "porque": f"Porque {i}"} for i in reversed(ids)]}
    monkeypatch.setattr(ia, "chamar_json", groq_falso)

    primeiro = _roteiro_ia(cli, cab, vid)
    assert primeiro["fonte"] == "ia" and len(pedidos) == 1
    segundo = _roteiro_ia(cli, cab, vid)
    assert len(pedidos) == 1  # mesmas escolhas, mesma saída, mesmo veículo: sem Groq
    assert segundo == primeiro

    _roteiro_ia(cli, cab, vid, saida="09:00")  # outra saída: outro roteiro
    assert len(pedidos) == 2

    cli.post("/swipe", json={"card": card(2), "tipo": "passo"}, headers=cab)  # mudou as escolhas
    terceiro = _roteiro_ia(cli, cab, vid)
    assert len(pedidos) == 3
    assert [c["id"] for c in terceiro["itens"]] == ["osm:node/3", "osm:node/1"]


def test_roteiro_do_plano_b_nao_vai_para_o_cache(pg, monkeypatch):
    from test_viagens import card, criar_e_coletar, resultado
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab, monkeypatch, resultado([card(1), card(2)], []))
    for i in (1, 2):
        cli.post("/swipe", json={"card": card(i), "gostou": True}, headers=cab)
    tentativas = []

    async def fora(client, **kw):
        tentativas.append(1)
        raise ia.IAIndisponivel("Groq 429")
    monkeypatch.setattr(ia, "chamar_json", fora)
    assert _roteiro_ia(cli, cab, vid)["fonte"] == "geometria"
    assert _roteiro_ia(cli, cab, vid)["fonte"] == "geometria"
    assert len(tentativas) == 2  # a segunda tenta a IA de novo
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from cache where chave like 'roteiro|%'").fetchone()[0] == 0


def test_chave_do_roteiro():
    base = [{"id": "osm:node/1", "horas_desde_saida": 0.5}, {"id": "osm:node/2", "horas_desde_saida": 2.0}]
    chave = ia.chave_roteiro(base, {"saida": "07:00", "veiculo": "carro", "dias": 1})
    assert chave.startswith("roteiro|") and "|07:00|carro|" in chave
    assert chave == ia.chave_roteiro(base, {"dias": 1, "veiculo": "carro", "saida": "07:00"})
    outras = [ia.chave_roteiro(base, {"saida": "08:00", "veiculo": "carro", "dias": 1}),
              ia.chave_roteiro(base, {"saida": "07:00", "veiculo": "moto", "dias": 1}),
              ia.chave_roteiro(base, {"saida": "07:00", "veiculo": "carro", "dias": 2}),
              ia.chave_roteiro(base[::-1], {"saida": "07:00", "veiculo": "carro", "dias": 1}),
              ia.chave_roteiro([{**base[0], "horas_desde_saida": 0.7}, base[1]],
                               {"saida": "07:00", "veiculo": "carro", "dias": 1})]
    assert len({chave, *outras}) == 6


