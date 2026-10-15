"""Achados da revisão final da branch organizacao-inicial."""
import asyncio
import json
import sqlite3

import httpx
import pytest

from app import ambiente, fila, ia, worker


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(fila, "DB", str(tmp_path / "f.db"))
    monkeypatch.setenv("GROQ_API_KEY", "teste")
    ia._limitadores.clear()


def _cliente_ia(conteudo):
    def h(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(conteudo)}}]})
    return httpx.AsyncClient(transport=httpx.MockTransport(h))


# 1. Pedido maior que o limite de tokens não pode quebrar
def test_limitador_pedido_maior_que_o_limite():
    assert ia.Limitador(tpm=8000).espera(9000) == float("inf")


def test_roteiro_grande_cai_no_plano_b_sem_500():
    from fastapi.testclient import TestClient
    from app.main import app
    cards = [{"id": f"c{i}", "nome": "Lugar com nome comprido " * 3, "descricao": "x" * 300,
              "horarios": {"segunda": ["11:30-14:00"] * 3}, "km_na_rota": float(i)} for i in range(80)]
    r = TestClient(app).post("/roteiro/carro", json={"cards": cards, "usar_ia": True})
    assert r.status_code == 200 and r.json()["fonte"] == "geometria"


# 2. Job preso em "rodando" volta para a fila
def test_jobs_presos_voltam_para_pendente():
    jid = fila.criar("carro", {})
    assert fila.pegar_proximo()["id"] == jid
    assert fila.recuperar_presos(minutos=0) == 1
    assert fila.obter(jid)["status"] == "pendente"
    assert fila.pegar_proximo()["id"] == jid


def test_job_recente_nao_e_recuperado():
    fila.criar("carro", {})
    fila.pegar_proximo()
    assert fila.recuperar_presos(minutos=30) == 0


# 3. Erro de banco não derruba o laço do worker
def test_laco_sobrevive_a_erro_do_banco(monkeypatch):
    chamadas = []
    def quebra():
        chamadas.append(1)
        if len(chamadas) == 1:
            raise sqlite3.OperationalError("database is locked")
        raise KeyboardInterrupt  # encerra o laço no teste
    monkeypatch.setattr(worker.fila, "pegar_proximo", quebra)
    monkeypatch.setattr(worker, "INTERVALO_S", 0)
    with pytest.raises(KeyboardInterrupt):
        asyncio.run(worker._laco())
    assert len(chamadas) == 2


# 5. .env carregado em execução local
def test_ambiente_carrega_sem_sobrescrever(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comentário\nPV_TESTE_A=um\nPV_TESTE_B = \"dois\"\n\nPV_TESTE_C=\nlinha ruim\n", encoding="utf-8")
    monkeypatch.setenv("PV_TESTE_A", "ja-tinha")
    monkeypatch.delenv("PV_TESTE_B", raising=False)
    monkeypatch.delenv("PV_TESTE_C", raising=False)
    ambiente.carregar(env)
    import os
    assert os.environ["PV_TESTE_A"] == "ja-tinha"
    assert os.environ["PV_TESTE_B"] == "dois"
    assert "PV_TESTE_C" not in os.environ
    monkeypatch.delenv("PV_TESTE_B")


def test_ambiente_sem_arquivo_nao_quebra(tmp_path):
    ambiente.carregar(tmp_path / "nao-existe.env")


def test_ambiente_procura_subindo_pastas(tmp_path):
    (tmp_path / ".env").write_text("X=1", encoding="utf-8")
    funda = tmp_path / "services" / "coletor"
    funda.mkdir(parents=True)
    assert ambiente.procurar(funda) == tmp_path / ".env"
    assert ambiente.procurar(funda, niveis=1) is None


# 6. /roteiro/carro sempre no mesmo formato
def test_roteiro_carro_mesmo_formato_sem_ia():
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app).post("/roteiro/carro", json={"cards": [{"id": "b", "km_na_rota": 5}, {"id": "a", "km_na_rota": 1}]}).json()
    assert [c["id"] for c in r["itens"]] == ["a", "b"] and r["fonte"] == "geometria" and r["explicacoes"] == {}


# 9. Resposta da IA sem os campos do schema cai no plano B
def test_ia_sem_campos_obrigatorios_cai_no_plano_b():
    cards = [{"id": "c0"}, {"id": "c1"}]
    async def go():
        async with _cliente_ia({"outra_coisa": 1}) as c:
            return await ia.ranquear(c, cards, "x"), await ia.ajustar_roteiro(c, cards, {})
    rank, rot = asyncio.run(go())
    assert [c["id"] for c in rank] == ["c0", "c1"] and rot["fonte"] == "geometria"


def test_triagem_fim_falso_sem_pergunta_termina():
    resp = [{"pergunta": "p", "resposta": "r"}]
    async def go():
        async with _cliente_ia({"pergunta": None, "opcoes": [], "fim": False, "resumo": "x"}) as c:
            return await ia.triagem(c, resp)
    r = asyncio.run(go())
    assert r["fim"] is True and r["pergunta"] is None
