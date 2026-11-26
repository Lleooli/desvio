"""Issue #43: eventos de produto e as seis metas do PRD."""
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import metricas, viagens
from app.main import app
from conftest import criar_pessoa
from test_migracoes import como

PEDIDO = {"origem": "Alegrete, RS", "destino": "Santa Maria, RS", "intervalo_km": 100}


def _eventos(pg, usuario: str) -> list[tuple]:
    with psycopg.connect(pg) as con:
        return [(r[0], r[1]) for r in con.execute(
            "select evento, dados from evento where usuario = %s order by criado_em, evento", (usuario,))]


def _coletada(viagem: str, *ids: int) -> None:
    """A busca da viagem terminou com estes cards, para o roteiro ter o que montar."""
    cards = [{"id": f"osm:node/{i}", "nome": f"Lugar {i}", "categoria": "turismo", "fonte": "openstreetmap",
              "lat": -29.7, "lon": -54.0, "km_na_rota": 10.0 * i, "horas_desde_saida": 0.2 * i} for i in ids]
    viagens.gravar_resultado(viagem, {"rota": {"distancia_km": 250, "duracao_h": 3.5}, "paradas": [
        {"nome": "Santa Maria", "uf": "RS", "lat": -29.68, "lon": -53.81, "tipo": "destino",
         "raio_km": 15, "km_na_rota": 250, "horas_desde_saida": 3.5, "cards": cards}]})


def test_migracao_cria_evento_so_para_o_servidor(pg):
    uid, _ = criar_pessoa(pg)
    with psycopg.connect(pg) as con:
        colunas = {r[0] for r in con.execute(
            "select column_name from information_schema.columns where table_name = 'evento'")}
        assert {"id", "usuario", "viagem", "evento", "dados", "criado_em"} <= colunas
    with psycopg.connect(pg) as con:
        como(con, uid)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            con.execute("select * from evento")


def test_fluxos_gravam_evento_sem_dado_pessoal(pg, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = cli.post("/viagem", json=PEDIDO, headers=cab).json()["viagem_id"]
    _coletada(vid, 1)
    assert cli.post("/swipe", json={"card": {"id": "osm:node/1", "nome": "Nome da pessoa", "categoria": "turismo"},
                                    "tipo": "favorito", "viagem": vid}, headers=cab).status_code == 200
    assert cli.post("/viagens/" + vid + "/roteiro", headers=cab).status_code == 200
    assert cli.post("/eventos", json={"evento": "roteiro_aberto_mapa", "viagem": vid, "app": "waze",
                                      "email": "a@b.c"}, headers=cab).status_code == 422
    assert cli.post("/eventos", json={"evento": "roteiro_aberto_mapa", "viagem": vid, "app": "waze"},
                    headers=cab).status_code == 200
    assert cli.post("/eventos", json={"evento": "primeiro_card", "viagem": vid, "tempo_ms": 1500},
                    headers=cab).status_code == 200
    resp = [{"pergunta": f"P{i}", "resposta": "Natureza"} for i in range(5)]
    assert cli.post("/triagem", json={"respostas": resp}, headers=cab).json()["fim"] is True
    assert cli.post("/triagem", json={"respostas": resp[:1], "pular": True}, headers=cab).json()["pulou"] is True

    gravados = dict(_eventos(pg, uid))
    assert set(gravados) >= {"viagem_criada", "swipe", "roteiro_montado", "roteiro_aberto_mapa",
                             "primeiro_card", "triagem_concluida", "triagem_pulada"}
    assert gravados["swipe"] == {"tipo": "favorito", "ordem": 0}
    assert gravados["roteiro_aberto_mapa"] == {"app": "waze"}
    assert gravados["primeiro_card"] == {"origem": "app", "tempo_ms": 1500}
    assert gravados["viagem_criada"] == {}
    assert "Nome da pessoa" not in str(gravados)


def test_roteiro_vazio_nao_conta_como_roteiro_montado(pg, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = cli.post("/viagem", json=PEDIDO, headers=cab).json()["viagem_id"]
    assert cli.post("/viagens/" + vid + "/roteiro", headers=cab).status_code == 200
    assert "roteiro_montado" not in dict(_eventos(pg, uid))


def test_falha_na_metrica_nao_quebra_o_swipe(pg, monkeypatch):
    def estoura(*a, **k):
        raise RuntimeError("banco de métrica fora")
    monkeypatch.setattr(metricas, "_gravar", estoura)
    _, cab = criar_pessoa(pg)
    r = TestClient(app).post("/swipe", json={"card": {"id": "osm:node/9"}, "tipo": "bora"}, headers=cab)
    assert r.status_code == 200
    with psycopg.connect(pg) as con:
        assert con.execute("select count(*) from evento").fetchone()[0] == 0


def test_painel_calcula_as_seis_metas(pg, monkeypatch):
    monkeypatch.setenv("PV_ADMIN_TOKEN", "segredo")
    a, cab_a = criar_pessoa(pg)
    b, cab_b = criar_pessoa(pg)
    cli = TestClient(app)
    va1 = cli.post("/viagem", json=PEDIDO, headers=cab_a).json()["viagem_id"]
    va2 = cli.post("/viagem", json=PEDIDO, headers=cab_a).json()["viagem_id"]
    vb = cli.post("/viagem", json=PEDIDO, headers=cab_b).json()["viagem_id"]
    _coletada(va2, 3, 4)

    def decide(cab, vid, i, tipo):
        assert cli.post("/swipe", json={"card": {"id": f"osm:node/{i}"}, "tipo": tipo, "viagem": vid},
                        headers=cab).status_code == 200

    decide(cab_a, va1, 1, "bora")
    decide(cab_a, va1, 2, "passo")
    decide(cab_a, va2, 3, "bora")
    decide(cab_a, va2, 4, "favorito")
    decide(cab_b, vb, 5, "passo")
    assert cli.post(f"/viagens/{va2}/roteiro", headers=cab_a).status_code == 200
    assert cli.post("/eventos", json={"evento": "roteiro_aberto_mapa", "viagem": va2, "app": "google"},
                    headers=cab_a).status_code == 200
    assert cli.post("/eventos", json={"evento": "primeiro_card", "viagem": va2, "tempo_ms": 4000},
                    headers=cab_a).status_code == 200
    assert cli.post("/eventos", json={"evento": "primeiro_card", "viagem": vb, "tempo_ms": 2000},
                    headers=cab_b).status_code == 200
    # o do servidor perde para o do app na mesma viagem
    metricas.registrar(a, "primeiro_card", va2, {"origem": "servidor", "tempo_ms": 9000})
    metricas.registrar(a, "triagem_concluida")
    metricas.registrar(b, "triagem_pulada")

    assert cli.get("/metricas").status_code == 404
    assert cli.get("/metricas", headers={"x-admin-token": "errado"}).status_code == 404
    monkeypatch.delenv("PV_ADMIN_TOKEN")
    assert cli.get("/metricas", headers={"x-admin-token": "segredo"}).status_code == 404
    monkeypatch.setenv("PV_ADMIN_TOKEN", "segredo")
    p = cli.get("/metricas", headers={"x-admin-token": "segredo"}).json()

    assert p["viagens_ate_roteiro"] == {"taxa": 0.3333, "meta": 0.6, "viagens": 3, "com_roteiro": 1}
    assert p["aceite"] == {"taxa": 0.6, "meta_min": 0.35, "meta_max": 0.5, "aceitos": 3, "swipes": 5}
    assert p["aceite_segunda_viagem"] == {"pontos": 50.0, "meta_pontos": 10, "pessoas": 1}
    assert p["roteiro_no_mapa"] == {"taxa": 1.0, "meta": 0.4, "abertos": 1, "roteiros": 1}
    assert p["tempo_primeiro_card"] == {"media_ms": 3000, "mediana_ms": 3000, "amostras": 2}
    assert p["triagem_sem_pular"] == {"taxa": 0.5, "meta": 0.7, "concluidas": 1, "puladas": 1}


def test_evento_de_outra_viagem_da_404(pg):
    _, cab_a = criar_pessoa(pg)
    _, cab_b = criar_pessoa(pg)
    cli = TestClient(app)
    vid = cli.post("/viagem", json=PEDIDO, headers=cab_a).json()["viagem_id"]
    assert cli.post("/eventos", json={"evento": "roteiro_aberto_mapa", "viagem": vid, "app": "google"},
                    headers=cab_b).status_code == 404
    assert cli.post("/eventos", json={"evento": "swipe", "viagem": vid}, headers=cab_a).status_code == 422
