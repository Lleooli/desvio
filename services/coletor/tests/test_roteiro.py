"""Issue #22: o roteiro da viagem de carro, com os lugares de Bora na ordem do km."""
from fastapi.testclient import TestClient

from app.main import app
from conftest import criar_pessoa
from test_viagens import card, criar_e_coletar, resultado


def test_roteiro_traz_os_aceitos_da_viagem_na_ordem_do_km(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    # O card 5 está numa parada anterior, mas tem km maior que o 3 e o 4 da parada seguinte
    vid = criar_e_coletar(cli, cab, monkeypatch,
                          resultado([card(5), card(1), card(2)], [card(4), card(3)]))
    for i, gostou in ((5, True), (1, True), (2, False), (4, True), (3, True)):
        cli.post("/swipe", json={"card": card(i), "gostou": gostou}, headers=cab)

    r = cli.post(f"/viagens/{vid}/roteiro", headers=cab)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["fonte"] == "geometria"
    assert [c["id"] for c in corpo["itens"]] == ["osm:node/1", "osm:node/3", "osm:node/4", "osm:node/5"]
    assert corpo["itens"][0]["km_na_rota"] == 10.0
    assert corpo["itens"][0]["horas_desde_saida"] == 0.2


def test_roteiro_fica_guardado_e_e_refeito_a_cada_montagem(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab, monkeypatch, resultado([card(1), card(2)], []))
    cli.post("/swipe", json={"card": card(2), "gostou": True}, headers=cab)
    cli.post(f"/viagens/{vid}/roteiro", headers=cab)
    cli.post("/swipe", json={"card": card(1), "gostou": True}, headers=cab)
    cli.post(f"/viagens/{vid}/roteiro", headers=cab)

    [v] = cli.get("/eu/exportar", headers=cab).json()["viagens"]
    assert [c["id"] for c in v["roteiro"]["itens"]] == ["osm:node/1", "osm:node/2"]
    assert v["roteiro"]["fonte"] == "geometria"


def test_roteiro_de_viagem_de_outra_pessoa_da_404(pg, monkeypatch):
    _, cab_a = criar_pessoa(pg)
    _, cab_b = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab_a, monkeypatch, resultado([card(1)], []))
    assert cli.post(f"/viagens/{vid}/roteiro", headers=cab_b).status_code == 404
    assert cli.post("/viagens/nao-e-uuid/roteiro", headers=cab_a).status_code == 404


def test_lugar_em_duas_paradas_sai_uma_vez_so_no_roteiro(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab, monkeypatch, resultado([card(1), card(2)], [card(2), card(3)]))
    for i in (1, 2, 3):
        cli.post("/swipe", json={"card": card(i), "gostou": True}, headers=cab)

    itens = cli.post(f"/viagens/{vid}/roteiro", headers=cab).json()["itens"]
    assert [c["id"] for c in itens] == ["osm:node/1", "osm:node/2", "osm:node/3"]
