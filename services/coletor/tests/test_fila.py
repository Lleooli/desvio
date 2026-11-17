import asyncio
import threading

import psycopg
import pytest

from app import fila, geo, worker


@pytest.fixture(autouse=True)
def banco(pg):
    return pg


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


def test_job_preso_volta_sem_progresso_nem_parcial(pg):
    jid = fila.criar("carro", {})
    fila.pegar_proximo()
    fila.progresso(jid, "lugares", "Buscando", "Cidade", 60)
    fila.parcial(jid, {"paradas": [{"cards": [{"id": "osm:1"}]}]})
    with psycopg.connect(pg, autocommit=True) as con:
        con.execute("update jobs set atualizado_em = now() - interval '2 hours' where id=%s", (jid,))
    assert fila.recuperar_presos(45) == 1
    j = fila.obter(jid)
    assert j["status"] == "pendente" and j["progresso"] is None and j["parcial"] is None


def test_job_fechado_nao_e_sobrescrito_por_execucao_repetida():
    jid = fila.criar("carro", {})
    fila.pegar_proximo()
    fila.concluir(jid, {"paradas": ["primeira"]})
    fila.falhar(jid, "segunda execução, atrasada")
    j = fila.obter(jid)
    assert j["status"] == "pronto" and j["resultado"] == {"paradas": ["primeira"]}


def test_obter_so_devolve_job_do_dono(pg):
    from conftest import criar_pessoa
    dono, _ = criar_pessoa(pg)
    outro, _ = criar_pessoa(pg)
    jid = fila.criar("viagem", {}, usuario=dono)
    assert fila.obter(jid, usuario=dono)["id"] == jid
    assert fila.obter(jid, usuario=outro) is None


def test_dois_workers_nunca_pegam_o_mesmo_job(pg):
    """Duas conexões abertas ao mesmo tempo: com o primeiro job travado pela transação de A,
    B pula para o próximo (SKIP LOCKED) em vez de esperar ou pegar o mesmo."""
    a, b = fila.criar("viagem", {}), fila.criar("viagem", {})
    sql = ("update jobs set status='rodando' where id = (select id from jobs where status='pendente' "
           "order by criado_em, id limit 1 for update skip locked) returning id")
    with psycopg.connect(pg) as con_a, psycopg.connect(pg) as con_b:
        pego_a = con_a.execute(sql).fetchone()[0]  # transação de A segue aberta
        pego_b = con_b.execute(sql).fetchone()[0]
        con_a.commit()
        con_b.commit()
    assert {pego_a, pego_b} == {a, b}


def test_muitos_workers_em_paralelo_dividem_a_fila(pg):
    ids = {fila.criar("viagem", {"n": i}) for i in range(40)}
    pegos: list[str] = []
    trava = threading.Lock()

    def trabalhar():
        while (job := fila.pegar_proximo()) is not None:
            with trava:
                pegos.append(job["id"])

    threads = [threading.Thread(target=trabalhar) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(pegos) == sorted(ids)  # todos pegos, nenhum repetido


def test_worker_processa(monkeypatch):
    async def falso(progresso=None, parcial=None, **kw):
        return {"modo": "carro", "paradas": [], "recebido": kw}
    monkeypatch.setattr(worker.coletor, "planejar_viagem", falso)
    jid = fila.criar("carro", {"origem": "A", "destino": "B"})
    assert asyncio.run(worker.rodar_uma_vez()) is True
    j = fila.obter(jid)
    assert j["status"] == "pronto" and j["resultado"]["recebido"]["origem"] == "A"
    assert asyncio.run(worker.rodar_uma_vez()) is False


def test_worker_marca_falha(monkeypatch):
    async def quebra(**kw):
        raise geo.LugarNaoEncontrado("Cidadezinha, XX")
    monkeypatch.setattr(worker.coletor, "planejar_viagem", quebra)
    ruim = fila.criar("carro", {"origem": "?", "destino": "?"})
    bom = fila.criar("tipo-desconhecido", {})
    assert asyncio.run(worker.rodar_uma_vez()) is True
    assert fila.obter(ruim)["status"] == "falhou"
    assert "Não achamos" in fila.obter(ruim)["erro"]
    assert asyncio.run(worker.rodar_uma_vez()) is True
    assert fila.obter(bom)["status"] == "falhou"
