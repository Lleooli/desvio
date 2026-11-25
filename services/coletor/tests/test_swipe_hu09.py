"""Issue #9 (HU09): decisão com tipo, viagem e parada, e desfazer."""
import psycopg
from fastapi.testclient import TestClient

from app.main import app
from conftest import criar_pessoa
from test_viagens import card, criar_e_coletar, resultado


def _linha(pg, usuario: str, lugar: str):
    with psycopg.connect(pg) as con:
        return con.execute(
            "select tipo, viagem::text, parada from decisao where usuario = %s and lugar = %s",
            (usuario, lugar)).fetchone()


def test_swipe_grava_bora_passo_e_favorito_com_viagem_e_parada(pg, monkeypatch):
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab, monkeypatch, resultado([card(1), card(2)], [card(3, "turismo")]))
    pedidos = ((1, "bora", 0), (2, "passo", 0), (3, "favorito", 1))
    for i, tipo, parada in pedidos:
        r = cli.post("/swipe", json={"card": card(i), "tipo": tipo, "viagem": vid, "parada": parada}, headers=cab)
        assert r.status_code == 200, r.text
        linha = _linha(pg, uid, f"osm:node/{i}")
        assert linha == (tipo, vid, parada)


def test_favorito_conta_como_aceite_no_perfil(pg):
    """Sem multiplicador no PRD: favorito entra na taxa como o bora (aceite 1, não 2)."""
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    for i, tipo in ((1, "favorito"), (2, "bora"), (3, "passo"), (4, "passo")):
        categoria = "restaurante" if i <= 2 else "posto"
        r = cli.post("/swipe", json={"card": card(i, categoria), "tipo": tipo}, headers=cab)
        assert r.status_code == 200
    p = cli.get("/perfil", headers=cab).json()
    assert p["total_swipes"] == 4 and p["aceitos"] == 2
    assert p["categoria"]["restaurante"] == {"aceitos": 2, "vistos": 2, "taxa": 1.0}
    assert p["categoria"]["posto"] == {"aceitos": 0, "vistos": 2, "taxa": 0.0}


def test_tipo_invalido_ou_ausente_da_422(pg):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    assert cli.post("/swipe", json={"card": card(1), "tipo": "amei"}, headers=cab).status_code == 422
    assert cli.post("/swipe", json={"card": card(1)}, headers=cab).status_code == 422
    assert cli.post("/swipe", json={"card": card(1), "gostou": False, "parada": 0}, headers=cab).status_code == 422


def test_viagem_alheia_ou_parada_inexistente_da_404(pg, monkeypatch):
    _, cab_a = criar_pessoa(pg)
    uid_b, cab_b = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab_a, monkeypatch, resultado([card(1)], []))
    assert cli.post("/swipe", json={"card": card(1), "tipo": "bora", "viagem": vid, "parada": 0},
                    headers=cab_b).status_code == 404
    assert cli.post("/swipe", json={"card": card(1), "tipo": "bora", "viagem": "nao-e-uuid", "parada": 0},
                    headers=cab_a).status_code == 404
    assert cli.post("/swipe", json={"card": card(1), "tipo": "bora", "viagem": vid, "parada": 9},
                    headers=cab_a).status_code == 404
    assert _linha(pg, uid_b, "osm:node/1") is None


def test_desfazer_devolve_o_card_e_recalcula_o_perfil(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab, monkeypatch, resultado([card(1, "turismo"), card(2, "turismo")], []))
    for i, tipo in ((1, "favorito"), (2, "bora")):
        assert cli.post("/swipe", json={"card": card(i, "turismo"), "tipo": tipo, "viagem": vid, "parada": 0},
                        headers=cab).status_code == 200

    antes = cli.get(f"/viagens/{vid}", headers=cab).json()
    assert antes["paradas"][0]["cards"] == []
    assert antes["progresso"] == {"decididos": 2, "total": 2}
    assert cli.get("/perfil", headers=cab).json()["aceitos"] == 2
    assert cli.get("/perfil", headers=cab).json()["categoria"]["turismo"]["taxa"] == 1.0

    r = cli.delete("/swipe/osm:node/1", headers=cab)
    assert r.status_code == 200 and r.json()["ok"] is True

    depois = cli.get(f"/viagens/{vid}", headers=cab).json()
    assert [c["id"] for c in depois["paradas"][0]["cards"]] == ["osm:node/1"]
    assert depois["progresso"] == {"decididos": 1, "total": 2}
    perfil = cli.get("/perfil", headers=cab).json()
    assert perfil["total_swipes"] == 1 and perfil["aceitos"] == 1
    assert "turismo" not in perfil["categoria"]  # a taxa só aparece com 2 ou mais vistos
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from lugar where id = 'osm:node/1'").fetchone()[0] == 1


def test_desfazer_sem_decisao_da_404_e_nao_mexe_na_decisao_alheia(pg):
    _, cab_a = criar_pessoa(pg)
    _, cab_b = criar_pessoa(pg)
    cli = TestClient(app)
    assert cli.post("/swipe", json={"card": card(1), "tipo": "favorito"}, headers=cab_a).status_code == 200
    assert cli.delete("/swipe/osm:node/1", headers=cab_b).status_code == 404
    assert cli.delete("/swipe/osm:node/99", headers=cab_a).status_code == 404
    assert cli.delete("/swipe/qualquer-coisa", headers=cab_a).status_code == 422
    assert cli.get("/perfil", headers=cab_a).json()["aceitos"] == 1
    assert cli.delete("/swipe/osm:node/1", headers=cab_a).status_code == 200
    assert cli.delete("/swipe/osm:node/1", headers=cab_a).status_code == 404
    assert cli.get("/perfil", headers=cab_a).json()["total_swipes"] == 0
