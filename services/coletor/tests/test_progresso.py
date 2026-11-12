"""Issue #5: progresso da busca por etapa em /jobs/{id}."""
import asyncio
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import coletor, fila, worker
from app.main import app


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(fila, "DB", str(tmp_path / "p.db"))


def test_textos_na_voz_do_design_system():
    assert coletor.texto_rota(2731.4, 35.2, "carro") == "2.731 km, uns 35h de estrada"
    assert coletor.texto_rota(90, 6.1, "bicicleta") == "90 km, uns 6h de pedal"
    assert coletor.texto_rota(12, 0.3, "moto") == "12 km, menos de 1h de estrada"
    assert coletor.texto_cidades(5, 200) == ("5 cidades para parar", "Uma a cada 200 km, mais o destino")
    assert coletor.texto_cidades(1, 1500)[0] == "1 cidade para parar"
    assert coletor.texto_cidades(1, 1500)[1] == "Uma a cada 1.500 km, mais o destino"
    assert coletor.texto_cidades(0, 200) == ("Nenhuma cidade no caminho", "Só o destino")


def test_worker_grava_as_etapas_e_api_devolve(monkeypatch):
    vistos = []

    async def falso(progresso=None, **kw):
        for etapa, pct in (("rota", 20), ("cidades", 35), ("lugares", 50), ("instagram", 90)):
            progresso(etapa, etapa.title(), f"detalhe de {etapa}", pct)
            vistos.append(fila.obter(jid)["progresso"])
        return {"veiculo": "carro", "paradas": []}
    monkeypatch.setattr(worker.coletor, "planejar_viagem", falso)
    jid = fila.criar("viagem", {"origem": "A", "destino": "B"})
    assert TestClient(app).get(f"/jobs/{jid}").json()["progresso"] is None
    asyncio.run(worker.rodar_uma_vez())

    assert [v["etapa"] for v in vistos] == ["rota", "cidades", "lugares", "instagram"]
    assert vistos[0] == {"etapa": "rota", "titulo": "Rota", "detalhe": "detalhe de rota", "percentual": 20}
    j = TestClient(app).get(f"/jobs/{jid}").json()
    assert j["status"] == "pronto" and j["progresso"]["etapa"] == "instagram"


def test_progresso_renova_atualizado_em_e_nao_mexe_em_job_fechado():
    jid = fila.criar("viagem", {})
    fila.pegar_proximo()
    antes = fila.obter(jid)["atualizado_em"]
    fila.progresso(jid, "rota", "Rota calculada", "10 km", 20)
    assert fila.obter(jid)["atualizado_em"] >= antes
    fila.concluir(jid, {"paradas": []})
    fila.progresso(jid, "cidades", "x", "y", 35)  # chegou atrasado: ignora
    assert fila.obter(jid)["progresso"]["etapa"] == "rota"


def test_erro_ao_gravar_progresso_nao_derruba_a_coleta():
    def quebra(*a):
        raise sqlite3.OperationalError("database is locked")
    coletor._avisar(quebra, "rota", "t", "d", 20)  # não levanta


def test_banco_antigo_sem_coluna_de_progresso(tmp_path, monkeypatch):
    velho = tmp_path / "velho.db"
    con = sqlite3.connect(velho)
    con.execute("""CREATE TABLE jobs (id TEXT PRIMARY KEY, tipo TEXT NOT NULL, entrada TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pendente', resultado TEXT, erro TEXT,
        criado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
        atualizado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')))""")
    con.execute("INSERT INTO jobs (id, tipo, entrada) VALUES ('j1', 'carro', '{}')")
    con.commit()
    con.close()
    monkeypatch.setattr(fila, "DB", str(velho))
    assert fila.obter("j1")["progresso"] is None
    fila.pegar_proximo()
    fila.progresso("j1", "rota", "Rota calculada", "1 km", 20)
    assert fila.obter("j1")["progresso"]["percentual"] == 20
