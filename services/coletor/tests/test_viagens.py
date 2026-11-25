"""Issue #4: viagens guardadas no banco e listadas por pessoa."""
import asyncio

import psycopg
from fastapi.testclient import TestClient

from app import worker
from app.main import app
from conftest import criar_pessoa

PEDIDO = {"origem": "Alegrete, RS", "destino": "Santa Maria, RS", "veiculo": "moto", "intervalo_km": 100}


def card(i: int, categoria: str = "restaurante", nota: float = 4.0, **extra) -> dict:
    return {"id": f"osm:node/{i}", "nome": f"Lugar {i}", "categoria": categoria, "nota": nota,
            "fonte": "openstreetmap", "lat": -29.7, "lon": -54.0, "km_na_rota": 10.0 * i,
            "horas_desde_saida": 0.2 * i, **extra}


def resultado(cards_1: list[dict], cards_2: list[dict]) -> dict:
    return {"veiculo": "moto", "intervalo_km": 100,
            "rota": {"distancia_km": 250, "duracao_h": 3.5, "polilinha": [[-29.78, -55.79], [-29.68, -53.81]]},
            "paradas": [
                {"nome": "São Vicente do Sul", "uf": "RS", "lat": -29.69, "lon": -54.68, "tipo": "parada",
                 "raio_km": 8, "km_na_rota": 110, "horas_desde_saida": 1.5, "cards": cards_1},
                {"nome": "Santa Maria", "uf": "RS", "lat": -29.68, "lon": -53.81, "tipo": "destino",
                 "raio_km": 15, "km_na_rota": 250, "horas_desde_saida": 3.5, "cards": cards_2},
            ]}


def coleta_falsa(monkeypatch, r: dict):
    async def falso(progresso=None, parcial=None, **kw):
        return r
    monkeypatch.setattr(worker.coletor, "planejar_viagem", falso)


def criar_e_coletar(cli, cab, monkeypatch, r: dict) -> str:
    resp = cli.post("/viagem", json=PEDIDO, headers=cab)
    assert resp.status_code == 202
    coleta_falsa(monkeypatch, r)
    assert asyncio.run(worker.rodar_uma_vez()) is True
    return resp.json()["viagem_id"]


def test_viagem_aparece_buscando_e_depois_pronta(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    resp = cli.post("/viagem", json=PEDIDO, headers=cab)
    assert resp.status_code == 202
    corpo = resp.json()
    assert corpo["viagem_id"] and corpo["job_id"]

    [v] = cli.get("/viagens", headers=cab).json()["viagens"]
    assert v["id"] == corpo["viagem_id"] and v["job_id"] == corpo["job_id"]
    assert v["status"] == "buscando"
    assert (v["origem"], v["destino"], v["veiculo"]) == ("Alegrete, RS", "Santa Maria, RS", "moto")
    assert v["progresso"] == {"decididos": 0, "total": 0}
    assert cli.get(f"/viagens/{v['id']}", headers=cab).json()["paradas"] == []

    coleta_falsa(monkeypatch, resultado([card(1), card(2)], [card(3)]))
    assert asyncio.run(worker.rodar_uma_vez()) is True
    [v] = cli.get("/viagens", headers=cab).json()["viagens"]
    assert v["status"] == "pronta"
    assert v["progresso"] == {"decididos": 0, "total": 3}
    assert cli.get(f"/jobs/{corpo['job_id']}", headers=cab).json()["status"] == "pronto"

    d = cli.get(f"/viagens/{v['id']}", headers=cab).json()
    assert d["polilinha"] == [[-29.78, -55.79], [-29.68, -53.81]]
    assert [(p["ordem"], p["nome"], p["uf"], p["tipo"]) for p in d["paradas"]] == [
        (0, "São Vicente do Sul", "RS", "parada"), (1, "Santa Maria", "RS", "destino")]
    assert [c["id"] for c in d["paradas"][0]["cards"]] == ["osm:node/1", "osm:node/2"]
    assert d["paradas"][1]["cards"][0]["km_na_rota"] == 30.0


def test_lista_mais_recente_primeiro(pg):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    ids = [cli.post("/viagem", json={**PEDIDO, "destino": d}, headers=cab).json()["viagem_id"]
           for d in ("Santa Maria, RS", "Porto Alegre, RS")]
    lista = cli.get("/viagens", headers=cab).json()["viagens"]
    assert [v["id"] for v in lista] == ids[::-1]


def test_cards_nao_trazem_lugares_ja_avaliados(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab, monkeypatch, resultado([card(1), card(2)], [card(3)]))
    assert cli.post("/swipe", json={"card": card(1), "gostou": True}, headers=cab).status_code == 200
    assert cli.post("/swipe", json={"card": card(3), "gostou": False}, headers=cab).status_code == 200

    d = cli.get(f"/viagens/{vid}", headers=cab).json()
    assert [c["id"] for p in d["paradas"] for c in p["cards"]] == ["osm:node/2"]
    assert d["progresso"] == {"decididos": 2, "total": 3}
    [v] = cli.get("/viagens", headers=cab).json()["viagens"]
    assert v["progresso"] == {"decididos": 2, "total": 3}


def test_cada_parada_traz_aceitos_e_total(pg, monkeypatch):
    """Issue #19: o contador "3 de 12" da tela Paradas conta Bora sobre todos os cards da parada."""
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab, monkeypatch, resultado([card(1), card(2), card(3)], [card(4)]))
    d = cli.get(f"/viagens/{vid}", headers=cab).json()
    assert [p["progresso"] for p in d["paradas"]] == [{"aceitos": 0, "total": 3}, {"aceitos": 0, "total": 1}]

    cli.post("/swipe", json={"card": card(1), "gostou": True}, headers=cab)
    cli.post("/swipe", json={"card": card(2), "gostou": False}, headers=cab)
    cli.post("/swipe", json={"card": card(4), "gostou": True}, headers=cab)
    d = cli.get(f"/viagens/{vid}", headers=cab).json()
    assert [p["progresso"] for p in d["paradas"]] == [{"aceitos": 1, "total": 3}, {"aceitos": 1, "total": 1}]


def test_cards_vem_ordenados_pelo_gosto(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    for i in (90, 91):  # o perfil só usa a taxa com 2 ou mais vistos
        cli.post("/swipe", json={"card": card(i, "posto"), "gostou": False}, headers=cab)
        cli.post("/swipe", json={"card": card(i + 10, "turismo"), "gostou": True}, headers=cab)
    vid = criar_e_coletar(cli, cab, monkeypatch,
                          resultado([card(1, "posto"), card(2, "turismo")], []))
    d = cli.get(f"/viagens/{vid}", headers=cab).json()
    assert [c["categoria"] for c in d["paradas"][0]["cards"]] == ["turismo", "posto"]


def test_cada_card_traz_o_horario_de_hoje(pg, monkeypatch):
    """Issue #28 (HU11): a folha do lugar mostra o horário de hoje, no fuso do lugar."""
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    todo_dia = {dia: ["11:30 – 23:00"] for dia in ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                                                    "sexta-feira", "sábado", "domingo")}
    vid = criar_e_coletar(cli, cab, monkeypatch,
                          resultado([card(1, uf="RS", horarios=todo_dia), card(2, uf="RS")], []))
    d = cli.get(f"/viagens/{vid}", headers=cab).json()
    assert [c["horario_hoje"] for c in d["paradas"][0]["cards"]] == [["11:30–23:00"], None]


def test_viagem_de_outra_pessoa_da_404(pg, monkeypatch):
    _, cab_a = criar_pessoa(pg)
    _, cab_b = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab_a, monkeypatch, resultado([card(1)], []))
    assert cli.get(f"/viagens/{vid}", headers=cab_b).status_code == 404
    assert cli.get("/viagens", headers=cab_b).json() == {"viagens": []}
    assert cli.get("/viagens/nao-e-uuid", headers=cab_a).status_code == 404


def test_coleta_que_quebra_marca_a_viagem_como_falhou(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    cli.post("/viagem", json=PEDIDO, headers=cab)

    async def quebra(**kw):
        raise ValueError("Não achamos essa cidade")
    monkeypatch.setattr(worker.coletor, "planejar_viagem", quebra)
    assert asyncio.run(worker.rodar_uma_vez()) is True
    [v] = cli.get("/viagens", headers=cab).json()["viagens"]
    assert v["status"] == "falhou"


def test_coleta_atualiza_o_lugar_e_guarda_o_km_fora_dele(pg, monkeypatch):
    """A coleta é dado do servidor: atualiza o lugar compartilhado; o km é só desta rota."""
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    cli.post("/swipe", json={"card": card(1, nome="Nome antigo"), "gostou": True}, headers=cab)
    criar_e_coletar(cli, cab, monkeypatch, resultado([card(1, nome="Nome novo")], []))
    with psycopg.connect(pg) as con:
        dados = con.execute("select dados from lugar where id = 'osm:node/1'").fetchone()[0]
    assert dados["nome"] == "Nome novo"
    assert "km_na_rota" not in dados and "horas_desde_saida" not in dados


def test_resultado_do_job_continua_igual(pg, monkeypatch):
    """O /jobs/{id} segue com o resultado personalizado, e gravar a viagem não tira cards dele."""
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    cli.post("/swipe", json={"card": card(2), "gostou": False}, headers=cab)
    resp = cli.post("/viagem", json=PEDIDO, headers=cab).json()
    coleta_falsa(monkeypatch, resultado([card(1), card(2)], []))
    asyncio.run(worker.rodar_uma_vez())
    j = cli.get(f"/jobs/{resp['job_id']}", headers=cab).json()
    assert [c["id"] for c in j["resultado"]["paradas"][0]["cards"]] == ["osm:node/1"]
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from parada_lugar").fetchone()[0] == 2


def gmaps(i: int, **extra) -> dict:
    return {**card(i, **extra), "id": f"gmaps:P{i}", "fonte": "google_maps"}


def test_parcial_abre_o_swipe_com_a_viagem_buscando_e_final_nao_repete(pg, monkeypatch):
    """#33: os cards do OpenStreetMap aparecem na viagem antes do Google; nenhum aparece duas vezes."""
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    resp = cli.post("/viagem", json=PEDIDO, headers=cab).json()
    vid = resp["viagem_id"]
    enquanto: list[dict] = []

    async def falso(progresso=None, parcial=None, **kw):
        parcial(resultado([card(1), card(2)], [card(3)]))
        d = cli.get(f"/viagens/{vid}", headers=cab).json()
        enquanto.append(d)
        # a pessoa desliza um card do parcial, com a viagem e a parada, enquanto o Google não chega
        r = cli.post("/swipe", json={"card": d["paradas"][0]["cards"][0], "tipo": "bora",
                                     "viagem": vid, "parada": 0}, headers=cab)
        assert r.status_code == 200, r.text
        enquanto.append(cli.get(f"/viagens/{vid}", headers=cab).json())
        # o final contém os cards do parcial (mesmos ids) mais os do Google
        return resultado([card(1), gmaps(7), card(2)], [card(3), gmaps(8)])
    monkeypatch.setattr(worker.coletor, "planejar_viagem", falso)
    assert asyncio.run(worker.rodar_uma_vez()) is True

    antes, depois_do_swipe = enquanto
    assert antes["status"] == "buscando"
    assert [[c["id"] for c in p["cards"]] for p in antes["paradas"]] == [["osm:node/1", "osm:node/2"], ["osm:node/3"]]
    assert antes["progresso"] == {"decididos": 0, "total": 3}
    assert [[c["id"] for c in p["cards"]] for p in depois_do_swipe["paradas"]] == [["osm:node/2"], ["osm:node/3"]]
    assert depois_do_swipe["paradas"][0]["progresso"] == {"aceitos": 1, "total": 2}

    final = cli.get(f"/viagens/{vid}", headers=cab).json()
    assert final["status"] == "pronta"
    ids = [c["id"] for p in final["paradas"] for c in p["cards"]]
    assert sorted(ids) == ["gmaps:P7", "gmaps:P8", "osm:node/2", "osm:node/3"]  # sem o já decidido
    assert len(ids) == len(set(ids))
    assert final["paradas"][0]["progresso"] == {"aceitos": 1, "total": 3}  # a decisão do parcial vale no final
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from parada_lugar where viagem = %s", (vid,)).fetchone()[0] == 5


def test_parcial_atrasado_nao_troca_as_paradas_finais(pg, monkeypatch):
    from app import viagens
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab, monkeypatch, resultado([card(1), gmaps(7)], [card(3)]))
    assert viagens.gravar_parcial(vid, resultado([card(1)], [])) is False
    d = cli.get(f"/viagens/{vid}", headers=cab).json()
    assert d["status"] == "pronta"
    assert [[c["id"] for c in p["cards"]] for p in d["paradas"]] == [["osm:node/1", "gmaps:P7"], ["osm:node/3"]]


def test_erro_ao_gravar_parcial_na_viagem_nao_derruba_a_coleta(pg, monkeypatch):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)

    def quebra(*a):
        raise psycopg.OperationalError("connection refused")
    monkeypatch.setattr(worker.viagens, "gravar_parcial", quebra)

    async def falso(progresso=None, parcial=None, **kw):
        parcial(resultado([card(1)], []))
        return resultado([card(1), gmaps(7)], [])
    resp = cli.post("/viagem", json=PEDIDO, headers=cab).json()
    monkeypatch.setattr(worker.coletor, "planejar_viagem", falso)
    asyncio.run(worker.rodar_uma_vez())
    assert cli.get(f"/viagens/{resp['viagem_id']}", headers=cab).json()["status"] == "pronta"
    assert cli.get(f"/jobs/{resp['job_id']}", headers=cab).json()["status"] == "pronto"
