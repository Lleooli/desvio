import json

from app import gmaps

ABOUT = json.dumps([
    {"id": "accessibility", "name": "Acessibilidade", "options": [
        {"name": "Entrada acessível", "enabled": True},
        {"name": "Banheiro acessível", "enabled": False}]},
    {"id": "service", "name": "Opções de serviço", "options": [
        {"name": "Refeição no local", "enabled": True},
        {"name": "Aceita pets", "enabled": True}]},
])


def test_sobre_so_opcoes_ativas():
    assert gmaps.sobre_de_about(ABOUT) == ["Entrada acessível", "Refeição no local", "Aceita pets"]


def test_sobre_invalido_ou_vazio():
    assert gmaps.sobre_de_about("") == []
    assert gmaps.sobre_de_about("não é json") == []
    assert gmaps.sobre_de_about('{"id": "x"}') == []


def test_sobre_limita_a_oito():
    muitas = json.dumps([{"options": [{"name": f"op{i}", "enabled": True} for i in range(12)]}])
    assert len(gmaps.sobre_de_about(muitas)) == 8


def test_linha_para_lugar_inclui_sobre():
    lugar = gmaps.linha_para_lugar({"title": "X", "about": ABOUT})
    assert lugar["sobre"][0] == "Entrada acessível"
