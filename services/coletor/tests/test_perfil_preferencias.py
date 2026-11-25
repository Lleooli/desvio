"""Issue #31: preferências do perfil (HU16, HU17) — tema, intervalo padrão e resumo editável."""
from fastapi.testclient import TestClient

from app import preferencias
from app.main import app
from conftest import criar_pessoa


def test_conta_nova_segue_o_sistema_e_nao_tem_intervalo_padrao(pg):
    _, cab = criar_pessoa(pg)
    perfil = TestClient(app).get("/perfil", headers=cab).json()
    assert perfil["tema"] == "sistema" and perfil["intervalo_km"] is None


def test_tema_escolhido_fica_guardado(pg):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    r = cli.patch("/perfil", json={"tema": "escuro"}, headers=cab)
    assert r.status_code == 200 and r.json()["tema"] == "escuro"
    assert cli.get("/perfil", headers=cab).json()["tema"] == "escuro"
    assert cli.patch("/perfil", json={"tema": "roxo"}, headers=cab).status_code == 422


def test_intervalo_padrao_fica_guardado_dentro_do_limite_da_viagem(pg):
    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    assert cli.patch("/perfil", json={"intervalo_km": 300}, headers=cab).json()["intervalo_km"] == 300
    assert cli.get("/perfil", headers=cab).json()["intervalo_km"] == 300
    for invalido in (5, 601, None):
        assert cli.patch("/perfil", json={"intervalo_km": invalido}, headers=cab).status_code == 422
    assert cli.patch("/perfil", json={"tema": None}, headers=cab).status_code == 422
    assert cli.get("/perfil", headers=cab).json()["intervalo_km"] == 300


def test_resumo_corrigido_substitui_o_da_ia_e_mantem_as_respostas(pg):
    uid, cab = criar_pessoa(pg)
    cli = TestClient(app)
    respostas = [{"pergunta": "Com quem?", "resposta": "Com o cachorro"}]
    preferencias.guardar_triagem(uid, None, respostas, "Gosta de praia.", pulou=False)
    r = cli.patch("/perfil", json={"resumo": "  Gosta de serra e viaja com pet.  "}, headers=cab).json()
    assert r["resumo"] == "Gosta de serra e viaja com pet." and r["respostas"] == respostas
    assert cli.patch("/perfil", json={"resumo": "   "}, headers=cab).json()["resumo"] is None
    assert cli.patch("/perfil", json={"resumo": "x" * 1001}, headers=cab).status_code == 422
