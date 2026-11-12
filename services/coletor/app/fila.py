"""Fila de jobs de coleta em SQLite.

A API cria o job e responde na hora; o worker (app/worker.py) pega o mais
antigo, roda a coleta e grava o resultado. A interface (criar, pegar_proximo,
concluir, falhar, obter) é a mesma que a versão em Postgres vai ter.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing

DB = os.getenv("PV_DB", "planejador.db")


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(DB, timeout=30)
    con.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, tipo TEXT NOT NULL, entrada TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pendente', resultado TEXT, erro TEXT,
        criado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
        atualizado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')), progresso TEXT)""")
    if DB not in _migrados:  # bancos criados antes da coluna de progresso
        if "progresso" not in {c[1] for c in con.execute("PRAGMA table_info(jobs)")}:
            con.execute("ALTER TABLE jobs ADD COLUMN progresso TEXT")
        _migrados.add(DB)
    return con


_migrados: set[str] = set()


def progresso(job_id: str, etapa: str, titulo: str, detalhe: str, percentual: int) -> None:
    """Grava a etapa atual da coleta (rota, cidades, lugares, instagram) para a tela Carregando.

    Também renova `atualizado_em`: job que avança não é confundido com job preso.
    """
    p = {"etapa": etapa, "titulo": titulo, "detalhe": detalhe, "percentual": percentual}
    with closing(_con()) as con, con:
        con.execute("UPDATE jobs SET progresso=?, atualizado_em=strftime('%Y-%m-%dT%H:%M:%f', 'now') "
                    "WHERE id=? AND status='rodando'", (json.dumps(p, ensure_ascii=False), job_id))


def criar(tipo: str, entrada: dict) -> str:
    jid = uuid.uuid4().hex
    with closing(_con()) as con, con:
        con.execute("INSERT INTO jobs (id, tipo, entrada) VALUES (?,?,?)",
                    (jid, tipo, json.dumps(entrada, ensure_ascii=False)))
    return jid


def pegar_proximo() -> dict | None:
    with closing(_con()) as con, con:
        linha = con.execute(
            "UPDATE jobs SET status='rodando', atualizado_em=strftime('%Y-%m-%dT%H:%M:%f', 'now') "
            "WHERE id = (SELECT id FROM jobs WHERE status='pendente' ORDER BY criado_em, rowid LIMIT 1) "
            "RETURNING id, tipo, entrada").fetchone()
    return {"id": linha[0], "tipo": linha[1], "entrada": json.loads(linha[2])} if linha else None


def recuperar_presos(minutos: float = 30) -> int:
    """Devolve à fila os jobs "rodando" sem atualização há `minutos` (worker morreu no meio)."""
    with closing(_con()) as con, con:
        cur = con.execute("UPDATE jobs SET status='pendente', atualizado_em=strftime('%Y-%m-%dT%H:%M:%f', 'now') "
                          "WHERE status='rodando' AND julianday('now') - julianday(atualizado_em) >= ?",
                          (minutos / 1440,))
    return cur.rowcount


def _fechar(job_id: str, status: str, resultado: dict | None, erro: str | None) -> None:
    with closing(_con()) as con, con:
        con.execute("UPDATE jobs SET status=?, resultado=?, erro=?, "
                    "atualizado_em=strftime('%Y-%m-%dT%H:%M:%f', 'now') WHERE id=?",
                    (status, json.dumps(resultado, ensure_ascii=False) if resultado is not None else None,
                     erro, job_id))


def concluir(job_id: str, resultado: dict) -> None:
    _fechar(job_id, "pronto", resultado, None)


def falhar(job_id: str, erro: str) -> None:
    _fechar(job_id, "falhou", None, erro)


def obter(job_id: str) -> dict | None:
    with closing(_con()) as con:
        l = con.execute("SELECT id, tipo, status, resultado, erro, criado_em, atualizado_em, progresso "
                        "FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not l:
        return None
    return {"id": l[0], "tipo": l[1], "status": l[2], "resultado": json.loads(l[3]) if l[3] else None,
            "erro": l[4], "criado_em": l[5], "atualizado_em": l[6],
            "progresso": json.loads(l[7]) if l[7] else None}
