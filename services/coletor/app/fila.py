"""Fila de jobs de coleta no Postgres (tabela `jobs`).

A API cria o job e responde na hora; o worker (app/worker.py) pega o mais
antigo com FOR UPDATE SKIP LOCKED, roda a coleta e grava o resultado. Dois
workers em paralelo nunca pegam o mesmo job.
"""
from __future__ import annotations

import uuid

from psycopg.types.json import Jsonb

from . import banco

_AGORA = "clock_timestamp()"  # now() é o início da transação; aqui queremos o instante real


def criar(tipo: str, entrada: dict, usuario: str | None = None) -> str:
    jid = uuid.uuid4().hex
    with banco.conectar() as con:
        con.execute("insert into jobs (id, usuario, tipo, entrada) values (%s, %s, %s, %s)",
                    (jid, usuario, tipo, Jsonb(entrada)))
    return jid


def pegar_proximo() -> dict | None:
    with banco.conectar() as con:
        l = con.execute(
            f"update jobs set status='rodando', atualizado_em={_AGORA} "
            "where id = (select id from jobs where status='pendente' order by criado_em, id "
            "            limit 1 for update skip locked) "
            "returning id, tipo, entrada").fetchone()
    return {"id": l["id"], "tipo": l["tipo"], "entrada": l["entrada"]} if l else None


def recuperar_presos(minutos: float = 30) -> int:
    """Devolve à fila os jobs "rodando" sem atualização há `minutos` (worker morreu no meio)."""
    with banco.conectar() as con:
        cur = con.execute(f"update jobs set status='pendente', atualizado_em={_AGORA} "
                          f"where status='rodando' and atualizado_em <= {_AGORA} - make_interval(secs => %s)",
                          (minutos * 60,))
    return cur.rowcount


def parcial(job_id: str, resultado: dict) -> None:
    """Resultado parcial (só OpenStreetMap) enquanto o Google Maps não chega."""
    with banco.conectar() as con:
        con.execute(f"update jobs set parcial=%s, atualizado_em={_AGORA} where id=%s and status='rodando'",
                    (Jsonb(resultado), job_id))


def progresso(job_id: str, etapa: str, titulo: str, detalhe: str, percentual: int) -> None:
    """Grava a etapa atual da coleta (rota, cidades, lugares, instagram) para a tela Carregando.

    Também renova `atualizado_em`: job que avança não é confundido com job preso.
    """
    p = {"etapa": etapa, "titulo": titulo, "detalhe": detalhe, "percentual": percentual}
    with banco.conectar() as con:
        con.execute(f"update jobs set progresso=%s, atualizado_em={_AGORA} where id=%s and status='rodando'",
                    (Jsonb(p), job_id))


def _fechar(job_id: str, status: str, resultado: dict | None, erro: str | None) -> None:
    with banco.conectar() as con:
        con.execute(f"update jobs set status=%s, resultado=%s, erro=%s, parcial=null, atualizado_em={_AGORA} "
                    "where id=%s",
                    (status, Jsonb(resultado) if resultado is not None else None, erro, job_id))


def concluir(job_id: str, resultado: dict) -> None:
    _fechar(job_id, "pronto", resultado, None)


def falhar(job_id: str, erro: str) -> None:
    _fechar(job_id, "falhou", None, erro)


def obter(job_id: str, usuario: str | None = None) -> dict | None:
    """O job; com `usuario`, só se for dele (o de outra pessoa volta None, como se não existisse)."""
    sql = ("select id, tipo, status, resultado, erro, criado_em, atualizado_em, progresso, parcial "
           "from jobs where id=%s")
    args: tuple = (job_id,)
    if usuario is not None:
        sql += " and usuario=%s"
        args += (usuario,)
    with banco.conectar() as con:
        l = con.execute(sql, args).fetchone()
    if not l:
        return None
    return {**l, "criado_em": l["criado_em"].isoformat(), "atualizado_em": l["atualizado_em"].isoformat()}
