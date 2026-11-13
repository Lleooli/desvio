"""Issue #1: schema do Supabase e RLS.

O fixture `_schema` (conftest) apaga tudo e roda as migrações do zero; aqui
conferimos as tabelas e a RLS fazendo o papel `authenticated` com o `sub` do
JWT em request.jwt.claims, como o PostgREST do Supabase faz.
"""
import json
import uuid

import psycopg
import pytest

from conftest import criar_pessoa


def como(con, uid: str | None):
    """Passa a agir como a pessoa `uid` (ou anônimo) até o fim da transação."""
    papel = "authenticated" if uid else "anon"
    con.execute(f"set local role {papel}")
    con.execute("select set_config('request.jwt.claims', %s, true)",
                (json.dumps({"sub": uid, "role": papel}) if uid else "",))


def test_tabelas_do_modelo_de_dados(pg):
    with psycopg.connect(pg) as con:
        nomes = {r[0] for r in con.execute(
            "select tablename from pg_tables where schemaname='public'")}
        sem_rls = [r[0] for r in con.execute(
            "select relname from pg_class where relnamespace='public'::regnamespace "
            "and relkind='r' and not relrowsecurity")]
    assert {"usuario", "viagem", "parada", "lugar", "decisao", "roteiro", "jobs", "cache"} <= nomes
    assert sem_rls == []


def test_conta_nova_cria_usuario(pg):
    uid, _ = criar_pessoa(pg)
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from usuario where id=%s", (uid,)).fetchone()[0] == 1


def test_criar_usuario_nao_fica_exposta_na_api(pg):
    with psycopg.connect(pg) as con:
        for papel in ("anon", "authenticated"):
            pode = con.execute("select has_function_privilege(%s, 'public.criar_usuario()', 'execute')",
                               (papel,)).fetchone()[0]
            assert not pode, papel


@pytest.fixture
def duas_viagens(pg):
    a, _ = criar_pessoa(pg)
    b, _ = criar_pessoa(pg)
    with psycopg.connect(pg) as con:
        ids = {}
        for uid in (a, b):
            vid = con.execute("insert into viagem (usuario, origem, destino, intervalo_km) "
                              "values (%s, 'A', 'B', 100) returning id", (uid,)).fetchone()[0]
            con.execute("insert into parada (viagem, ordem, cidade) values (%s, 1, 'C')", (vid,))
            con.execute("insert into roteiro (viagem) values (%s)", (vid,))
            con.execute("insert into lugar (id, dados) values (%s, '{}') on conflict do nothing", ("osm:node/1",))
            con.execute("insert into decisao (usuario, lugar, viagem, tipo) values (%s, 'osm:node/1', %s, 'bora')",
                        (uid, vid))
            con.execute("insert into jobs (id, usuario, tipo, entrada) values (%s, %s, 'viagem', '{}')",
                        (uuid.uuid4().hex, uid))
            ids[uid] = vid
    return a, b, ids


def test_rls_cada_um_so_le_o_que_e_seu(pg, duas_viagens):
    a, b, ids = duas_viagens
    with psycopg.connect(pg) as con:
        como(con, a)
        assert [r[0] for r in con.execute("select id from viagem")] == [ids[a]]
        assert [r[0] for r in con.execute("select viagem from parada")] == [ids[a]]
        assert [r[0] for r in con.execute("select viagem from roteiro")] == [ids[a]]
        assert [r[0] for r in con.execute("select usuario from decisao")] == [uuid.UUID(a)]
        assert [r[0] for r in con.execute("select usuario from jobs")] == [uuid.UUID(a)]
        assert [r[0] for r in con.execute("select id from usuario")] == [uuid.UUID(a)]
        assert con.execute("select count(*) from lugar").fetchone()[0] == 1  # leitura pública
    with psycopg.connect(pg) as con:
        como(con, a)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):  # cache é só do servidor
            con.execute("select * from cache")


def test_rls_nao_deixa_mexer_no_dos_outros(pg, duas_viagens):
    a, b, ids = duas_viagens
    with psycopg.connect(pg) as con:
        como(con, a)
        assert con.execute("update viagem set origem='X' where id=%s", (ids[b],)).rowcount == 0
        assert con.execute("delete from decisao where usuario=%s", (b,)).rowcount == 0
    with psycopg.connect(pg) as con:
        como(con, a)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):  # viagem em nome de outra pessoa
            con.execute("insert into viagem (usuario, origem, destino, intervalo_km) values (%s, 'A', 'B', 1)", (b,))
    with psycopg.connect(pg) as con:
        como(con, a)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):  # job só o servidor cria
            con.execute("insert into jobs (id, usuario, tipo, entrada) values ('x', %s, 'viagem', '{}')", (a,))


def test_rls_decisao_nao_aponta_para_viagem_dos_outros(pg, duas_viagens):
    a, b, ids = duas_viagens
    with psycopg.connect(pg) as con:
        con.execute("insert into lugar (id, dados) values ('osm:node/2', '{}')")
    with psycopg.connect(pg) as con:
        como(con, a)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            con.execute("insert into decisao (usuario, lugar, viagem, tipo) values (%s, 'osm:node/2', %s, 'bora')",
                        (a, ids[b]))
    with psycopg.connect(pg) as con:
        como(con, a)
        con.execute("insert into decisao (usuario, lugar, viagem, tipo) values (%s, 'osm:node/2', %s, 'bora')",
                    (a, ids[a]))


def test_anonimo_so_le_lugar(pg, duas_viagens):
    with psycopg.connect(pg) as con:
        como(con, None)
        assert con.execute("select count(*) from lugar").fetchone()[0] == 1
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            con.execute("select * from viagem")


def test_apagar_conta_apaga_tudo_da_pessoa(pg, duas_viagens):
    """Base da LGPD (#40): apagar em auth.users leva viagens, decisões e jobs junto."""
    a, b, _ = duas_viagens
    with psycopg.connect(pg) as con:
        con.execute("delete from auth.users where id=%s", (a,))
        for tabela in ("viagem", "decisao", "jobs", "usuario"):
            col = "id" if tabela == "usuario" else "usuario"
            assert con.execute(f"select count(*) from {tabela} where {col}=%s", (a,)).fetchone()[0] == 0
        assert con.execute("select count(*) from viagem where usuario=%s", (b,)).fetchone()[0] == 1
