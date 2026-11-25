"""Issue #8: triagem em usuario.perfil_gosto e ranqueamento dos cards (HU02, HU18)."""
import asyncio

import psycopg
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app import ia, preferencias, worker
from app.main import app
from conftest import criar_pessoa
from test_viagens import PEDIDO, card, coleta_falsa, resultado


def _respostas(n: int) -> list[dict]:
    return [{"pergunta": f"Pergunta {i}", "resposta": f"Resposta {i}"} for i in range(n)]


def _rodar(cli, cab, monkeypatch, cards) -> dict:
    resp = cli.post("/viagem", json=PEDIDO, headers=cab)
    assert resp.status_code == 202, resp.text
    coleta_falsa(monkeypatch, resultado(cards, []))
    assert asyncio.run(worker.rodar_uma_vez()) is True
    return resp.json()


def test_triagem_concluida_aparece_no_perfil_e_nao_apaga_o_resto(pg, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app)
    with psycopg.connect(pg) as con:
        con.execute("update usuario set perfil_gosto = %s where id = %s", (Jsonb({"outro": "fica"}), uid))
    assert cli.post("/triagem", json={"respostas": []}, headers=cab).json()["fim"] is False
    with psycopg.connect(pg) as con:
        assert con.execute("select perfil_gosto from usuario where id = %s", (uid,)).fetchone()[0] == {"outro": "fica"}

    resp = _respostas(5)
    r = cli.post("/triagem", json={"respostas": resp}, headers=cab)
    assert r.status_code == 200 and r.json()["fim"] is True
    assert r.json()["resumo"] == ia.resumo_simples(resp)
    perfil = cli.get("/perfil", headers=cab).json()
    assert perfil["resumo"] == r.json()["resumo"] and perfil["respostas"] == resp and perfil["pulou"] is False
    with psycopg.connect(pg) as con:
        gosto = con.execute("select perfil_gosto from usuario where id = %s", (uid,)).fetchone()[0]
    assert gosto["outro"] == "fica" and gosto["resumo"] == r.json()["resumo"] and gosto["respostas"] == resp


def test_pular_guarda_o_que_ja_foi_respondido_sem_resumo(pg, monkeypatch):
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app)

    async def nao_chama(*a, **k):
        raise AssertionError("Pular não chama a IA")

    monkeypatch.setattr(ia, "triagem", nao_chama)
    resp = _respostas(2)
    r = cli.post("/triagem", json={"respostas": resp, "pular": True}, headers=cab)
    assert r.status_code == 200 and r.json()["pulou"] is True and r.json()["resumo"] is None
    perfil = cli.get("/perfil", headers=cab).json()
    assert perfil["respostas"] == resp and perfil["resumo"] is None and perfil["pulou"] is True
    assert preferencias.perfil(uid)["respostas"] == resp


def test_job_sem_resumo_fica_na_estatistica_e_nao_chama_a_ia(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    for i in (90, 91):  # a taxa só entra com 2 ou mais vistos
        cli.post("/swipe", json={"card": card(i, "posto", nota=5), "gostou": False}, headers=cab)
        cli.post("/swipe", json={"card": card(i + 10, "turismo", nota=5), "gostou": True}, headers=cab)

    def nao_chama(*a, **k):
        raise AssertionError("sem resumo não chama o ranqueamento")

    monkeypatch.setattr(ia, "_ranquear_pela_ia", nao_chama)
    corpo = _rodar(cli, cab, monkeypatch, [card(1, "posto", nota=5), card(2, "turismo", nota=1)])
    ids = [c["id"] for c in cli.get(f"/jobs/{corpo['job_id']}", headers=cab).json()["resultado"]["paradas"][0]["cards"]]
    assert ids == ["osm:node/2", "osm:node/1"]


def test_job_com_resumo_ranqueia_os_30_e_a_segunda_viagem_usa_o_cache(pg, monkeypatch):
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app)
    resumo = "Gosta de natureza e viaja com pet."
    preferencias.guardar_triagem(uid, None, _respostas(1), resumo, pulou=False)
    chamadas = []

    async def inverte(client, cards, texto):
        chamadas.append(texto)
        assert len(cards) == ia.MAX_RANQUEAR
        return list(reversed(cards))

    monkeypatch.setattr(ia, "_ranquear_pela_ia", inverte)
    cards = [card(i, "turismo", nota=100 - i) for i in range(32)]
    corpo = _rodar(cli, cab, monkeypatch, cards)
    ordem = [f"osm:node/{i}" for i in range(29, -1, -1)] + ["osm:node/30", "osm:node/31"]
    assert [c["id"] for c in cli.get(f"/jobs/{corpo['job_id']}", headers=cab).json()
            ["resultado"]["paradas"][0]["cards"]] == ordem
    assert [c["id"] for c in cli.get(f"/viagens/{corpo['viagem_id']}", headers=cab).json()
            ["paradas"][0]["cards"]] == ordem
    assert chamadas == [resumo]
    with psycopg.connect(pg) as con:
        chaves = [r[0] for r in con.execute("select chave from cache where chave like 'ranque|%'")]
    assert len(chaves) == 1 and chaves[0].startswith("ranque|saovicentedosul|turismo|")

    segundo = _rodar(cli, cab, monkeypatch, cards)
    assert chamadas == [resumo]
    assert [c["id"] for c in cli.get(f"/jobs/{segundo['job_id']}", headers=cab).json()
            ["resultado"]["paradas"][0]["cards"]] == ordem

    preferencias.guardar_triagem(uid, None, _respostas(1), "Outro resumo.", pulou=False)
    _rodar(cli, cab, monkeypatch, cards)
    assert chamadas == [resumo, "Outro resumo."]


def test_plano_b_do_ranqueamento_nao_vai_para_o_cache(pg, monkeypatch):
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app)
    resumo = "Gosta de natureza."
    preferencias.guardar_triagem(uid, None, _respostas(1), resumo, pulou=False)
    chamadas = []

    async def sem_ia(client, cards, texto):
        chamadas.append(texto)
        return None  # Groq fora do ar, 429 ou tempo esgotado

    monkeypatch.setattr(ia, "_ranquear_pela_ia", sem_ia)
    cards = [card(i, "turismo", nota=100 - i) for i in range(5)]
    _rodar(cli, cab, monkeypatch, cards)
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from cache where chave like 'ranque|%'").fetchone()[0] == 0
    _rodar(cli, cab, monkeypatch, cards)
    assert chamadas == [resumo, resumo]  # a segunda viagem tenta a IA de novo


def test_ranqueamento_continua_depois_do_primeiro_swipe(pg, monkeypatch):
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app)
    preferencias.guardar_triagem(uid, None, _respostas(1), "Gosta de natureza.", pulou=False)

    async def inverte(client, cards, texto):
        return list(reversed(cards))

    monkeypatch.setattr(ia, "_ranquear_pela_ia", inverte)
    cards = [card(i, "turismo", nota=100 - i) for i in range(32)]
    corpo = _rodar(cli, cab, monkeypatch, cards)
    primeiro = cli.get(f"/viagens/{corpo['viagem_id']}", headers=cab).json()["paradas"][0]["cards"][0]
    assert primeiro["id"] == "osm:node/29"
    assert cli.post("/swipe", json={"card": primeiro, "tipo": "passo"}, headers=cab).status_code == 200
    ids = [c["id"] for c in cli.get(f"/viagens/{corpo['viagem_id']}", headers=cab).json()["paradas"][0]["cards"]]
    assert ids == [f"osm:node/{i}" for i in range(28, -1, -1)] + ["osm:node/30", "osm:node/31"]
