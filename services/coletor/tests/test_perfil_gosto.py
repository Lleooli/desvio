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

    monkeypatch.setattr(ia, "_ranquear_lote_pela_ia", nao_chama)
    corpo = _rodar(cli, cab, monkeypatch, [card(1, "posto", nota=5), card(2, "turismo", nota=1)])
    ids = [c["id"] for c in cli.get(f"/jobs/{corpo['job_id']}", headers=cab).json()["resultado"]["paradas"][0]["cards"]]
    assert ids == ["osm:node/2", "osm:node/1"]


def _ranqueada(cards: list[dict]) -> dict:
    """Resultado da coleta com a parada já na ordem genérica da IA (parada_cidade, #93)."""
    r = resultado(cards, [])
    r["paradas"][0]["ranqueada"] = True
    return r


def _rodar_ranqueada(cli, cab, monkeypatch, cards) -> dict:
    resp = cli.post("/viagem", json=PEDIDO, headers=cab)
    assert resp.status_code == 202, resp.text
    coleta_falsa(monkeypatch, _ranqueada(cards))
    assert asyncio.run(worker.rodar_uma_vez()) is True
    return resp.json()


def _sem_ia(monkeypatch) -> None:
    def nao_chama(*a, **k):
        raise AssertionError("o gosto da pessoa entra sem IA (#93)")
    monkeypatch.setattr(ia, "_ranquear_lote_pela_ia", nao_chama)
    monkeypatch.setattr(ia, "chamar_json", nao_chama)


def test_job_com_resumo_nao_chama_a_ia_e_mantem_a_ordem_generica(pg, monkeypatch):
    """#93: a IA ordena a cidade uma vez, sem o gosto de ninguém; o resumo não gera chamada nova."""
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app)
    preferencias.guardar_triagem(uid, None, _respostas(1), "Gosta de natureza e viaja com pet.", pulou=False)
    _sem_ia(monkeypatch)
    # a ordem genérica é a inversa da nota: a posição vale mais que a nota na conta
    cards = [card(i, "turismo", nota=4 + i / 100) for i in range(5)]
    corpo = _rodar_ranqueada(cli, cab, monkeypatch, cards)
    ordem = [f"osm:node/{i}" for i in range(5)]
    assert [c["id"] for c in cli.get(f"/jobs/{corpo['job_id']}", headers=cab).json()
            ["resultado"]["paradas"][0]["cards"]] == ordem
    assert [c["id"] for c in cli.get(f"/viagens/{corpo['viagem_id']}", headers=cab).json()
            ["paradas"][0]["cards"]] == ordem


def test_gosto_da_pessoa_entra_por_cima_da_ordem_generica(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    for i in (90, 91):  # a taxa só entra com 2 ou mais vistos
        cli.post("/swipe", json={"card": card(i, "turismo"), "gostou": False}, headers=cab)
        cli.post("/swipe", json={"card": card(i + 10, "posto"), "gostou": True}, headers=cab)
    _sem_ia(monkeypatch)
    corpo = _rodar_ranqueada(cli, cab, monkeypatch, [card(1, "turismo"), card(2, "turismo"), card(3, "posto")])
    ids = [c["id"] for c in cli.get(f"/jobs/{corpo['job_id']}", headers=cab).json()["resultado"]["paradas"][0]["cards"]]
    assert ids == ["osm:node/3", "osm:node/1", "osm:node/2"]  # o posto sobe; os turismos ficam na ordem da IA


def test_ordem_generica_continua_depois_do_primeiro_swipe(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    _sem_ia(monkeypatch)
    cards = [card(i, "turismo", nota=4 + i / 100) for i in range(32)]
    corpo = _rodar_ranqueada(cli, cab, monkeypatch, cards)
    primeiro = cli.get(f"/viagens/{corpo['viagem_id']}", headers=cab).json()["paradas"][0]["cards"][0]
    assert primeiro["id"] == "osm:node/0"
    assert cli.post("/swipe", json={"card": primeiro, "tipo": "passo"}, headers=cab).status_code == 200
    ids = [c["id"] for c in cli.get(f"/viagens/{corpo['viagem_id']}", headers=cab).json()["paradas"][0]["cards"]]
    assert ids == [f"osm:node/{i}" for i in range(1, 32)]


def test_triagem_refeita_pelo_perfil_substitui_a_antiga(pg, monkeypatch):
    """HU03: as respostas novas substituem as antigas; o job não manda o resumo à IA (#93)."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    antigas = _respostas(5)
    novas = [{**r, "resposta": f"Nova {i}"} for i, r in enumerate(antigas)]
    assert cli.post("/triagem", json={"respostas": antigas}, headers=cab).status_code == 200
    r = cli.post("/triagem", json={"respostas": novas}, headers=cab).json()
    assert r["fim"] is True

    perfil = cli.get("/perfil", headers=cab).json()
    assert perfil["respostas"] == novas and perfil["resumo"] == r["resumo"] == ia.resumo_simples(novas)

    _sem_ia(monkeypatch)
    _rodar(cli, cab, monkeypatch, [card(i, "turismo", nota=5) for i in range(3)])
