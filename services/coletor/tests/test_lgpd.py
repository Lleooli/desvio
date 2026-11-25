"""Issue #40 (LGPD): exportar os dados e apagar a conta."""
import asyncio

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import conta, worker
from app.main import app
from conftest import criar_pessoa
from test_viagens import card, criar_e_coletar, resultado

URL = "https://projeto.supabase.co"
CHAVE = "chave-service-role-de-teste"


@pytest.fixture
def admin(pg, monkeypatch):
    """Admin API do Supabase de mentira: ao apagar, tira a conta do auth.users de teste.

    `admin.falhar = True` faz ela responder 500, como o Supabase fora do ar.
    """
    class Admin:
        falhar = False
        chamadas: list[httpx.Request] = []

    def responder(req: httpx.Request) -> httpx.Response:
        Admin.chamadas.append(req)
        if Admin.falhar:
            return httpx.Response(500, json={"msg": "fora do ar"})
        uid = req.url.path.rsplit("/", 1)[-1]
        with psycopg.connect(pg, autocommit=True) as con:
            con.execute("delete from auth.users where id = %s", (uid,))
        return httpx.Response(200, json={})

    monkeypatch.setattr(conta, "SUPABASE_URL", URL)
    monkeypatch.setattr(conta, "SERVICE_ROLE_KEY", CHAVE)
    monkeypatch.setattr(conta, "_transporte", httpx.MockTransport(responder))
    return Admin


def contar(pg, tabela: str, onde: str = "", args: tuple = ()) -> int:
    with psycopg.connect(pg) as con:
        return con.execute(f"select count(*) from {tabela} {onde}", args).fetchone()[0]


def apagar(cli, cab, confirmar="APAGAR"):
    return cli.request("DELETE", "/eu", json={"confirmar": confirmar}, headers=cab)


def pessoa_com_dados(pg, monkeypatch) -> tuple[str, dict, str]:
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app)
    vid = criar_e_coletar(cli, cab, monkeypatch, resultado([card(1), card(2)], [card(3)]))
    for i in (1, 2):
        cli.post("/swipe", json={"card": card(i, "turismo"), "gostou": i == 1}, headers=cab)
    with psycopg.connect(pg, autocommit=True) as con:
        con.execute("insert into roteiro (viagem, itens, fonte) values (%s, %s, 'geometria')",
                    (vid, psycopg.types.json.Jsonb([{"id": "osm:node/1"}])))
    return uid, cab, vid


# Exportar

def test_exportacao_contem_viagens_decisoes_e_perfil(pg, monkeypatch):
    uid, cab, vid = pessoa_com_dados(pg, monkeypatch)
    r = TestClient(app).get("/eu/exportar", headers=cab)
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    d = r.json()
    assert d["usuario"]["email"] == f"{uid[:8]}@teste.dev"
    assert {"email", "provedor", "perfil_gosto", "tema", "intervalo_km", "criado_em"} <= d["usuario"].keys()
    assert d["perfil"]["total_swipes"] == 2 and d["perfil"]["aceitos"] == 1
    [v] = d["viagens"]
    assert v["id"] == vid and v["status"] == "pronta" and v["origem"] == "Alegrete, RS"
    assert [p["cidade"] for p in v["paradas"]] == ["São Vicente do Sul", "Santa Maria"]
    assert [c["id"] for c in v["paradas"][0]["cards"]] == ["osm:node/1", "osm:node/2"]
    assert v["roteiro"]["itens"] == [{"id": "osm:node/1"}]
    assert sorted((x["lugar"], x["tipo"]) for x in d["decisoes"]) == [("osm:node/1", "bora"),
                                                                     ("osm:node/2", "passo")]
    [busca] = d["buscas"]  # o job com origem e destino digitados também é dado da pessoa
    assert busca["entrada"]["origem"] == "Alegrete, RS" and busca["status"] == "pronto"


def test_exportacao_traz_tema_intervalo_e_resumo_do_perfil(pg, monkeypatch):
    _, cab, _ = pessoa_com_dados(pg, monkeypatch)
    cli = TestClient(app)
    r = cli.patch("/perfil", json={"tema": "escuro", "intervalo_km": 300, "resumo": "Gosto de mirantes"},
                  headers=cab)
    assert r.status_code == 200
    d = cli.get("/eu/exportar", headers=cab).json()
    assert d["usuario"]["tema"] == "escuro" and d["usuario"]["intervalo_km"] == 300
    assert d["perfil"]["tema"] == "escuro" and d["perfil"]["intervalo_km"] == 300
    assert d["perfil"]["resumo"] == "Gosto de mirantes"
    assert d["usuario"]["perfil_gosto"]["resumo"] == "Gosto de mirantes"


def test_depois_de_apagar_o_login_nao_traz_tema_nem_resumo_antigos(pg, monkeypatch, admin):
    _, cab, _ = pessoa_com_dados(pg, monkeypatch)
    cli = TestClient(app)
    cli.patch("/perfil", json={"tema": "escuro", "intervalo_km": 300, "resumo": "Gosto de mirantes"}, headers=cab)
    assert apagar(cli, cab).status_code == 200
    _, cab_novo = criar_pessoa(pg)
    p = cli.get("/perfil", headers=cab_novo).json()
    assert p["tema"] == "sistema" and p["resumo"] is None and p["respostas"] == []
    assert p["intervalo_km"] in (None, 200)


def test_exportacao_so_traz_os_dados_de_quem_pede(pg, monkeypatch):
    pessoa_com_dados(pg, monkeypatch)
    _, cab_b = criar_pessoa(pg)
    d = TestClient(app).get("/eu/exportar", headers=cab_b).json()
    assert d["viagens"] == [] and d["decisoes"] == [] and d["buscas"] == [] and d["perfil"]["total_swipes"] == 0


# Apagar

@pytest.mark.parametrize("corpo", [{"confirmar": "apagar"}, {"confirmar": ""}, {}])
def test_apagar_exige_confirmacao(pg, admin, corpo):
    uid, cab = criar_pessoa(pg)
    r = TestClient(app).request("DELETE", "/eu", json=corpo, headers=cab)
    assert r.status_code == 422
    assert contar(pg, "usuario", "where id = %s", (uid,)) == 1
    assert admin.chamadas == []


def test_apagar_remove_tudo_e_chama_a_admin_api(pg, monkeypatch, admin):
    uid, cab, _ = pessoa_com_dados(pg, monkeypatch)
    _, cab_b, vid_b = pessoa_com_dados(pg, monkeypatch)  # outra pessoa, que não pode perder nada
    cli = TestClient(app)
    r = apagar(cli, cab)
    assert r.status_code == 200 and r.json() == {"dados": "apagados", "conta": "apagada"}

    [req] = admin.chamadas
    assert req.method == "DELETE" and str(req.url) == f"{URL}/auth/v1/admin/users/{uid}"
    assert req.headers["apikey"] == CHAVE and req.headers["authorization"] == f"Bearer {CHAVE}"
    for tabela in ("usuario where id = %s", "viagem where usuario = %s", "decisao where usuario = %s",
                   "jobs where usuario = %s", "exclusao_pendente where usuario = %s", "auth.users where id = %s"):
        nome, onde = tabela.split(" ", 1)
        assert contar(pg, nome, onde, (uid,)) == 0, nome
    assert contar(pg, "parada") == 2 and contar(pg, "roteiro") == 1  # as da outra pessoa
    assert cli.get(f"/viagens/{vid_b}", headers=cab_b).status_code == 200
    assert contar(pg, "lugar") == 3  # lugares são compartilhados, não são dado pessoal


def test_depois_de_apagar_o_token_antigo_da_401_e_o_login_cria_conta_vazia(pg, monkeypatch, admin):
    _, cab, _ = pessoa_com_dados(pg, monkeypatch)
    cli = TestClient(app)
    assert apagar(cli, cab).status_code == 200
    # o token antigo ainda vale por até 1 h, mas a conta não existe mais
    r = cli.post("/viagem", json={"origem": "A, RS", "destino": "B, RS", "intervalo_km": 100}, headers=cab)
    assert r.status_code == 401
    assert cli.get("/eu/exportar", headers=cab).status_code == 401
    # entrar de novo cria uma conta nova no Supabase Auth; o gatilho cria a linha em usuario, vazia
    novo, cab_novo = criar_pessoa(pg)
    d = cli.get("/eu/exportar", headers=cab_novo).json()
    assert d["usuario"] is not None and d["viagens"] == [] and d["decisoes"] == []
    assert d["perfil"]["total_swipes"] == 0
    assert cli.get("/viagens", headers=cab_novo).json() == {"viagens": []}


def test_admin_api_fora_do_ar_apaga_os_dados_e_deixa_pendente(pg, monkeypatch, admin):
    uid, cab, _ = pessoa_com_dados(pg, monkeypatch)
    admin.falhar = True
    cli = TestClient(app)
    r = apagar(cli, cab)
    assert r.status_code == 200 and r.json() == {"dados": "apagados", "conta": "pendente"}
    assert contar(pg, "usuario", "where id = %s", (uid,)) == 0
    assert contar(pg, "viagem") == 0 and contar(pg, "decisao") == 0 and contar(pg, "jobs") == 0
    with psycopg.connect(pg) as con:
        p = con.execute("select tentativas, ultimo_erro from exclusao_pendente where usuario = %s",
                        (uid,)).fetchone()
    assert p[0] == 1 and "500" in p[1]
    assert contar(pg, "auth.users", "where id = %s", (uid,)) == 1

    # a conta ainda existe no Auth, mas o token não recria a linha em usuario
    r = cli.post("/swipe", json={"card": card(1), "gostou": True}, headers=cab)
    assert r.status_code == 401
    assert contar(pg, "usuario", "where id = %s", (uid,)) == 0

    # o worker tenta de novo; com o Supabase de volta, a exclusão termina
    worker.completar_exclusoes()
    assert contar(pg, "exclusao_pendente") == 1  # ainda fora do ar
    admin.falhar = False
    worker.completar_exclusoes()
    assert contar(pg, "exclusao_pendente") == 0
    assert contar(pg, "auth.users", "where id = %s", (uid,)) == 0


def test_sem_service_role_a_exclusao_fica_pendente(pg):
    uid, cab = criar_pessoa(pg)
    r = apagar(TestClient(app), cab)
    assert r.json()["conta"] == "pendente"
    with psycopg.connect(pg) as con:
        erro = con.execute("select ultimo_erro from exclusao_pendente where usuario = %s", (uid,)).fetchone()[0]
    assert "SUPABASE_SERVICE_ROLE_KEY" in erro


def test_admin_api_responde_404_conta_ja_apagada(pg, monkeypatch):
    uid, cab = criar_pessoa(pg)
    monkeypatch.setattr(conta, "SUPABASE_URL", URL)
    monkeypatch.setattr(conta, "SERVICE_ROLE_KEY", CHAVE)
    monkeypatch.setattr(conta, "_transporte", httpx.MockTransport(lambda req: httpx.Response(404)))
    assert apagar(TestClient(app), cab).json()["conta"] == "apagada"
    assert contar(pg, "exclusao_pendente") == 0


def test_job_rodando_de_conta_apagada_nao_quebra_o_worker(pg, monkeypatch, admin):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    cli.post("/viagem", json={"origem": "A, RS", "destino": "B, RS", "intervalo_km": 100}, headers=cab)
    assert apagar(cli, cab).status_code == 200
    assert asyncio.run(worker.rodar_uma_vez()) is False  # o job foi junto com a conta


def test_link_de_exportar_baixa_uma_vez_sem_o_token(pg, monkeypatch):
    _, cab, _ = pessoa_com_dados(pg, monkeypatch)
    cli = TestClient(app)
    r = cli.post("/eu/exportar/link", headers=cab)
    assert r.status_code == 200 and r.json()["valido_min"] == 10
    caminho = r.json()["caminho"]
    arquivo = cli.get(caminho)  # sem Authorization: o navegador não tem o token
    assert arquivo.status_code == 200
    assert "attachment" in arquivo.headers["content-disposition"]
    sem_hora = lambda d: {k: v for k, v in d.items() if k != "exportado_em"}  # noqa: E731
    assert sem_hora(arquivo.json()) == sem_hora(cli.get("/eu/exportar", headers=cab).json())
    assert cli.get(caminho).status_code == 404  # uso único
    assert cli.get("/eu/exportar/arquivo/inventado").status_code == 404
    assert cli.post("/eu/exportar/link").status_code == 401
