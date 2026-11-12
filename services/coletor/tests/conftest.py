import os
import time
import uuid

import pytest

# Os testes não leem o .env de quem roda: resultado igual em qualquer máquina.
os.environ["PV_ENV_FILE"] = ""

# Postgres de teste (sem internet): `docker compose --profile teste up -d banco-teste` e
# PV_TEST_DATABASE_URL=postgresql://postgres:teste@localhost:54329/desvio_teste
# Sem ela, os testes que precisam de banco são pulados; no CI ela sempre existe.
PG = os.getenv("PV_TEST_DATABASE_URL", "")
SEGREDO = "segredo-de-teste-com-mais-de-32-caracteres"


@pytest.fixture(autouse=True)
def _isolado(monkeypatch):
    """Por padrão, nenhum teste fala com banco de verdade nem com o Supabase."""
    from app import auth, banco
    monkeypatch.setattr(banco, "URL", "")
    monkeypatch.setattr(auth, "SUPABASE_URL", "")
    monkeypatch.setattr(auth, "JWT_SECRET", SEGREDO)


@pytest.fixture(scope="session")
def _schema():
    if not PG:
        if os.getenv("CI"):  # no CI os testes de banco nunca podem sumir em silêncio
            pytest.fail("PV_TEST_DATABASE_URL não configurada no CI")
        pytest.skip("PV_TEST_DATABASE_URL não configurada (veja tests/conftest.py)")
    import psycopg
    from app import banco
    with psycopg.connect(PG, autocommit=True) as con:  # do zero: prova que as migrações rodam num banco vazio
        con.execute("drop schema if exists public cascade; drop schema if exists auth cascade; create schema public")
    banco.aplicar_migracoes(PG, com_auth_local=True)
    return PG


@pytest.fixture
def pg(_schema, monkeypatch):
    """Banco limpo para o teste, já ligado em app.banco."""
    import psycopg
    from app import banco
    with psycopg.connect(_schema, autocommit=True) as con:
        con.execute("truncate jobs, cache, decisao, lugar, roteiro, parada, viagem, usuario, auth.users cascade")
    monkeypatch.setattr(banco, "URL", _schema)
    return _schema


def token(uid: str, segundos: int = 3600, **extra) -> str:
    import jwt
    agora = int(time.time())
    dados = {"sub": uid, "aud": "authenticated", "role": "authenticated", "iat": agora,
             "exp": agora + segundos, "email": f"{uid[:8]}@teste.dev", **extra}
    return jwt.encode(dados, SEGREDO, algorithm="HS256")


def criar_pessoa(url: str) -> tuple[str, dict]:
    """Conta nova no auth.users de mentira (o gatilho cria a linha em usuario); devolve id e cabeçalho."""
    import psycopg
    uid = str(uuid.uuid4())
    with psycopg.connect(url, autocommit=True) as con:
        con.execute("insert into auth.users (id, email) values (%s, %s)", (uid, f"{uid[:8]}@teste.dev"))
    return uid, {"Authorization": f"Bearer {token(uid)}"}


@pytest.fixture
def pessoa(pg):
    return criar_pessoa(pg)
