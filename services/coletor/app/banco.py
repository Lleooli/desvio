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


class ContaApagada(RuntimeError):
    """O token ainda vale (até 1 h), mas a conta já saiu de auth.users; a API responde 401."""


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
    Conta apagada com o token ainda válido: `usuario` aponta para auth.users e o
    insert quebra a chave estrangeira; vira ContaApagada. Também vira ContaApagada a
    conta com exclusão pendente (app/conta.py): ela ainda está em auth.users, mas a
    pessoa pediu para apagar, e a linha em `usuario` não pode voltar.
    """
    if con is None:
        with conectar() as nova:
            return garantir_usuario(usuario, email, nova)
    try:
        cur = con.execute("insert into usuario (id, email) select %s, %s where not exists "
                          "(select 1 from exclusao_pendente where usuario = %s) on conflict (id) do nothing",
                          (usuario, email, usuario))
    except psycopg.errors.ForeignKeyViolation:
        raise ContaApagada(usuario) from None
    if cur.rowcount == 0 and not con.execute("select 1 from usuario where id = %s", (usuario,)).fetchone():
        raise ContaApagada(usuario)


def aplicar_migracoes(url: str, com_auth_local: bool = False) -> None:
    """Roda as migrações em ordem. `com_auth_local` cria antes o schema auth de mentira
    (infra/supabase/local/00_auth.sql), para um Postgres puro; nunca no Supabase."""
    arquivos = sorted((MIGRACOES / "migrations").glob("*.sql"))
    if com_auth_local:
        arquivos.insert(0, MIGRACOES / "local" / "00_auth.sql")
    with psycopg.connect(url, autocommit=True) as con:
        for arq in arquivos:
            con.execute(arq.read_text(encoding="utf-8"))
