import asyncio

import pytest

from app import fila, worker


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(fila, "DB", str(tmp_path / "fila.db"))


def test_ciclo_de_vida():
    jid = fila.criar("carro", {"origem": "A", "destino": "B"})
    assert fila.obter(jid)["status"] == "pendente"
    job = fila.pegar_proximo()
    assert job == {"id": jid, "tipo": "carro", "entrada": {"origem": "A", "destino": "B"}}
    assert fila.obter(jid)["status"] == "rodando"
    fila.concluir(jid, {"paradas": []})
    j = fila.obter(jid)
    assert j["status"] == "pronto" and j["resultado"] == {"paradas": []} and j["erro"] is None


def test_fila_nao_entrega_duas_vezes():
    a = fila.criar("carro", {})
    b = fila.criar("carro", {})
    assert [fila.pegar_proximo()["id"], fila.pegar_proximo()["id"]] == [a, b]
    assert fila.pegar_proximo() is None


def test_obter_inexistente():
    assert fila.obter("nao-existe") is None


def test_worker_processa(monkeypatch):
    async def falso(**kw):
        return {"modo": "carro", "paradas": [], "recebido": kw}
    monkeypatch.setattr(worker.coletor, "planejar_viagem", falso)
    jid = fila.criar("carro", {"origem": "A", "destino": "B"})
    assert asyncio.run(worker.rodar_uma_vez()) is True
    j = fila.obter(jid)
    assert j["status"] == "pronto" and j["resultado"]["recebido"]["origem"] == "A"
    assert asyncio.run(worker.rodar_uma_vez()) is False


def test_worker_marca_falha(monkeypatch):
    async def quebra(**kw):
        raise ValueError("Não achamos essa cidade")
    monkeypatch.setattr(worker.coletor, "planejar_viagem", quebra)
    ruim = fila.criar("carro", {"origem": "?", "destino": "?"})
    bom = fila.criar("tipo-desconhecido", {})
    assert asyncio.run(worker.rodar_uma_vez()) is True
    assert fila.obter(ruim)["status"] == "falhou"
    assert "Não achamos" in fila.obter(ruim)["erro"]
    assert asyncio.run(worker.rodar_uma_vez()) is True
    assert fila.obter(bom)["status"] == "falhou"
