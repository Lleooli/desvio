"""Issue #39 (HU07): token do Expo Push e aviso quando a busca termina."""
import asyncio
import json

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import fila, push, worker
from app.main import app
from conftest import criar_pessoa

TOKEN = "ExponentPushToken[abcdefghij]"
TOKEN_NOVO = "ExpoPushToken[zzzzzzzzzz]"


def test_migracao_guarda_so_token_do_expo(pg):
    uid, _ = criar_pessoa(pg)
    with psycopg.connect(pg) as con:
        colunas = {r[0] for r in con.execute(
            "select column_name from information_schema.columns where table_name = 'usuario'")}
        assert "expo_push_token" in colunas
        con.execute("update usuario set expo_push_token = %s where id = %s", (TOKEN, uid))
        assert con.execute("select expo_push_token from usuario where id = %s", (uid,)).fetchone()[0] == TOKEN
    with psycopg.connect(pg) as con:
        with pytest.raises(psycopg.errors.CheckViolation):
            con.execute("update usuario set expo_push_token = 'pessoa@email.com' where id = %s", (uid,))


def test_registra_atualiza_e_limpa_o_token(pg):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    assert cli.post("/eu/push-token", json={"token": TOKEN}, headers=cab).status_code == 200
    assert cli.post("/eu/push-token", json={"token": TOKEN_NOVO}, headers=cab).status_code == 200
    with psycopg.connect(pg) as con:
        assert con.execute("select expo_push_token from usuario where email like %s", ("%teste.dev",)).fetchone()[0] == TOKEN_NOVO
    assert cli.post("/eu/push-token", json={"token": None}, headers=cab).status_code == 200
    assert cli.post("/eu/push-token", json={"token": "nao-e-token"}, headers=cab).status_code == 422
    assert cli.post("/eu/push-token", json={"token": TOKEN, "email": "a@b.c"}, headers=cab).status_code == 422
    with psycopg.connect(pg) as con:
        assert con.execute("select expo_push_token from usuario where email like %s", ("%teste.dev",)).fetchone()[0] is None


def _enfileirar(pg, token: str | None) -> tuple[str, str]:
    uid, _ = criar_pessoa(pg)
    with psycopg.connect(pg) as con:
        if token:
            con.execute("update usuario set expo_push_token = %s where id = %s", (token, uid))
        vid = str(con.execute(
            "insert into viagem (usuario, origem, destino, intervalo_km) "
            "values (%s, 'Alegrete, RS', 'Vitória da Conquista, BA', 100) returning id", (uid,)).fetchone()[0])
    fila.criar("viagem", {"origem": "Alegrete, RS", "destino": "Vitória da Conquista, BA",
                          "usuario": uid, "viagem": vid}, usuario=uid)
    return uid, vid


def _sem_coleta(monkeypatch):
    async def pronto(job):
        return {"paradas": []}
    monkeypatch.setattr(worker, "processar", pronto)


def test_job_pronto_avisa_com_destino_e_viagem(pg, monkeypatch):
    _sem_coleta(monkeypatch)
    _, vid = _enfileirar(pg, TOKEN)
    enviados = []

    def receber(req: httpx.Request) -> httpx.Response:
        enviados.append(json.loads(req.content))
        assert req.url == httpx.URL(push.URL_EXPO)
        return httpx.Response(200, json={"data": {"status": "ok"}})

    monkeypatch.setattr(push, "_transporte", httpx.MockTransport(receber))
    assert asyncio.run(worker.rodar_uma_vez()) is True
    aviso = enviados[0]
    assert aviso["to"] == TOKEN
    assert aviso["title"] == "Paradas prontas"
    assert aviso["body"] == "Suas paradas para Vitória da Conquista estão prontas"
    assert aviso["data"]["viagem_id"] == vid
    assert aviso["data"]["rota"] == f"/viagens/{vid}/paradas"
    assert aviso["channelId"] == "busca"
    jid = aviso["data"]["job_id"]
    assert fila.obter(jid)["status"] == "pronto"


def test_falha_no_expo_nao_falha_o_job(pg, monkeypatch):
    _sem_coleta(monkeypatch)
    _enfileirar(pg, TOKEN)

    def sem_rede(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(push, "_transporte", httpx.MockTransport(sem_rede))
    assert asyncio.run(worker.rodar_uma_vez()) is True
    with psycopg.connect(pg) as con:
        assert con.execute("select status from jobs").fetchone()[0] == "pronto"


def test_expo_recusa_o_aparelho_e_o_job_fica_pronto(pg, monkeypatch):
    _sem_coleta(monkeypatch)
    _enfileirar(pg, TOKEN)

    def recusa(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"status": "error", "message": "DeviceNotRegistered",
                                                  "details": {"error": "DeviceNotRegistered"}}})

    monkeypatch.setattr(push, "_transporte", httpx.MockTransport(recusa))
    assert asyncio.run(worker.rodar_uma_vez()) is True
    with psycopg.connect(pg) as con:
        assert con.execute("select status from jobs").fetchone()[0] == "pronto"


def test_sem_token_nao_chama_o_expo(pg, monkeypatch):
    _sem_coleta(monkeypatch)
    _enfileirar(pg, None)

    def nao_chamar(req: httpx.Request) -> httpx.Response:
        raise AssertionError("não havia token")

    monkeypatch.setattr(push, "_transporte", httpx.MockTransport(nao_chamar))
    assert asyncio.run(worker.rodar_uma_vez()) is True
    with psycopg.connect(pg) as con:
        assert con.execute("select status from jobs").fetchone()[0] == "pronto"


def test_job_que_falha_nao_avisa(pg, monkeypatch):
    async def quebra(job):
        raise RuntimeError("coleta")
    monkeypatch.setattr(worker, "processar", quebra)
    _enfileirar(pg, TOKEN)
    chamou = []
    monkeypatch.setattr(push, "_transporte", httpx.MockTransport(lambda req: chamou.append(req) or httpx.Response(200)))
    assert asyncio.run(worker.rodar_uma_vez()) is True
    assert chamou == []
    with psycopg.connect(pg) as con:
        assert con.execute("select status from jobs").fetchone()[0] == "falhou"
