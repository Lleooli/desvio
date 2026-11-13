"""Conexão com o Postgres (Supabase em produção, o do docker compose em casa).

PV_DATABASE_URL é a connection string do Postgres. No Supabase, use a do pooler
em modo sessão ou transação; por isso `prepare_threshold=None` (o pgbouncer em
modo transação não guarda prepared statements).

A API e o worker conectam como dono das tabelas, então a RLS não se aplica a
eles: quem garante que cada pessoa só vê o que é dela é o código (o usuário sai
do token, app/auth.py). A RLS protege o acesso direto com a chave anônima.
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

URL = os.getenv("PV_DATABASE_URL", "")
MIGRACOES = Path(__file__).resolve().parents[3] / "infra" / "supabase"


class SemBanco(RuntimeError):
    pass


def conectar(autocommit: bool = False) -> psycopg.Connection:
    """Conexão nova; `with banco.conectar() as con:` faz commit no fim e fecha."""
    if not URL:
        raise SemBanco("PV_DATABASE_URL não configurada (veja o .env.example)")
    return psycopg.connect(URL, connect_timeout=5, prepare_threshold=None, row_factory=dict_row,
                           autocommit=autocommit)


def garantir_usuario(usuario: str, email: str | None = None, con: psycopg.Connection | None = None) -> None:
    """Cria a linha em `usuario` se a conta ainda não tem (o gatilho do Supabase Auth
    normalmente já criou; aqui cobre contas antigas e o Postgres local).

    Com `con`, roda na transação de quem chamou (o /swipe grava tudo numa só).
    """
    sql = "insert into usuario (id, email) values (%s, %s) on conflict (id) do nothing"
    if con is not None:
        con.execute(sql, (usuario, email))
        return
    with conectar() as nova:
        nova.execute(sql, (usuario, email))


def aplicar_migracoes(url: str, com_auth_local: bool = False) -> None:
    """Roda as migrações em ordem. `com_auth_local` cria antes o schema auth de mentira
    (infra/supabase/local/00_auth.sql), para um Postgres puro; nunca no Supabase."""
    arquivos = sorted((MIGRACOES / "migrations").glob("*.sql"))
    if com_auth_local:
        arquivos.insert(0, MIGRACOES / "local" / "00_auth.sql")
    with psycopg.connect(url, autocommit=True) as con:
        for arq in arquivos:
            con.execute(arq.read_text(encoding="utf-8"))
