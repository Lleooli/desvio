"""Achados da revisão do #58: swipe, conexão com o Postgres e erros de autenticação."""
import psycopg
from fastapi.testclient import TestClient

from app import preferencias
from app.main import app
from conftest import criar_pessoa

CARD = {"id": "gmaps:P1", "nome": "Churrascaria Gaúcha", "categoria": "restaurante", "tipo": "churrascaria",
        "faixa_preco": "$$", "nota": 4.7, "fonte": "google_maps"}


# Issue #61: o swipe não reescreve o lugar compartilhado

def test_swipe_com_card_alterado_nao_muda_o_lugar_gravado(pg):
    _, cab_a = criar_pessoa(pg)
    _, cab_b = criar_pessoa(pg)
    cli = TestClient(app)
    assert cli.post("/swipe", json={"card": CARD, "gostou": True}, headers=cab_a).status_code == 200
    falso = {**CARD, "nome": "Golpe", "foto": "https://golpe/x.jpg", "categoria": "posto"}
    assert cli.post("/swipe", json={"card": falso, "gostou": True}, headers=cab_b).status_code == 200
    with psycopg.connect(pg) as con:
        dados = con.execute("select dados from lugar where id = %s", (CARD["id"],)).fetchone()[0]
    assert dados["nome"] == "Churrascaria Gaúcha" and dados["categoria"] == "restaurante"
    assert "foto" not in dados


def test_perfil_de_outra_pessoa_nao_muda_com_o_swipe_alterado(pg):
    a, cab_a = criar_pessoa(pg)
    _, cab_b = criar_pessoa(pg)
    cli = TestClient(app)
    for i in range(2):  # a taxa só aparece com 2 ou mais vistos
        cli.post("/swipe", json={"card": {**CARD, "id": f"gmaps:P{i}"}, "gostou": True}, headers=cab_a)
    antes = preferencias.perfil(a)
    assert antes["categoria"]["restaurante"]["aceitos"] == 2
    # B chega primeiro num lugar novo e depois em um que A já viu, sempre com o card adulterado
    for i in (1, 9):
        falso = {**CARD, "id": f"gmaps:P{i}", "categoria": "posto", "tipo": "posto", "faixa_preco": "$$$$"}
        cli.post("/swipe", json={"card": falso, "gostou": False}, headers=cab_b)
    assert preferencias.perfil(a) == antes


def test_perfil_usa_o_card_que_a_propria_pessoa_viu(pg):
    """Quem chegou primeiro no lugar não decide a categoria que entra no perfil dos outros."""
    _, cab_a = criar_pessoa(pg)
    b, cab_b = criar_pessoa(pg)
    cli = TestClient(app)
    for i in range(2):
        falso = {**CARD, "id": f"gmaps:P{i}", "categoria": "posto"}
        cli.post("/swipe", json={"card": falso, "gostou": False}, headers=cab_a)
    for i in range(2):
        cli.post("/swipe", json={"card": {**CARD, "id": f"gmaps:P{i}"}, "gostou": True}, headers=cab_b)
    p = preferencias.perfil(b)
    assert p["categoria"] == {"restaurante": {"aceitos": 2, "vistos": 2, "taxa": 1.0}}


def test_decisao_antiga_sem_card_usa_o_lugar(pg):
    a, _ = criar_pessoa(pg)
    with psycopg.connect(pg) as con:
        for i in range(2):
            con.execute("insert into lugar (id, dados) values (%s, %s)",
                        (f"osm:node/{i}", psycopg.types.json.Jsonb({"categoria": "turismo"})))
            con.execute("insert into decisao (usuario, lugar, tipo) values (%s, %s, 'bora')", (a, f"osm:node/{i}"))
    assert preferencias.perfil(a)["categoria"] == {"turismo": {"aceitos": 2, "vistos": 2, "taxa": 1.0}}


# Issue #62: o /swipe grava numa conexão e numa transação só

def test_swipe_grava_em_uma_conexao_e_uma_transacao(pg, monkeypatch):
    from app import banco
    a, cab = criar_pessoa(pg)
    with psycopg.connect(pg, autocommit=True) as con:
        con.execute("delete from usuario where id = %s", (a,))  # conta antiga, sem a linha em usuario
    original, conexoes = banco.conectar, []

    def contando(*a, **k):
        con = original(*a, **k)
        conexoes.append(con)
        return con
    monkeypatch.setattr(banco, "conectar", contando)
    assert TestClient(app).post("/swipe", json={"card": CARD, "gostou": True}, headers=cab).status_code == 200
    assert len(conexoes) == 1
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from usuario where id = %s", (a,)).fetchone()[0] == 1
        assert con.execute("select count(*) from decisao where usuario = %s", (a,)).fetchone()[0] == 1


def test_swipe_que_falha_no_meio_nao_deixa_nada_gravado(pg, monkeypatch):
    """Na mesma transação: se a decisão não grava, a linha em usuario também não fica."""
    a, cab = criar_pessoa(pg)
    with psycopg.connect(pg, autocommit=True) as con:
        con.execute("delete from usuario where id = %s", (a,))
    monkeypatch.setattr(preferencias, "CAMPOS_PERFIL", None)  # quebra o registrar depois do garantir_usuario
    r = TestClient(app, raise_server_exceptions=False).post("/swipe", json={"card": CARD, "gostou": True},
                                                            headers=cab)
    assert r.status_code == 500
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from usuario where id = %s", (a,)).fetchone()[0] == 0
        assert con.execute("select count(*) from lugar").fetchone()[0] == 0
