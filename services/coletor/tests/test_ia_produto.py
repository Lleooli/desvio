import asyncio
import json

import httpx
import pytest

from app import ia

CARDS = [{"id": f"c{i}", "nome": f"Lugar {i}", "categoria": "restaurante", "nota": 4.5,
          "avaliacoes": 100, "descricao": "x" * 300, "sobre": ["Aceita pets"], "km_na_rota": i * 10.0}
         for i in range(35)]


@pytest.fixture(autouse=True)
def limpa(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "teste")
    ia._limitadores.clear()


def rodar(coro_fn, conteudo=None, falha=False):
    enviados = []
    def h(req):
        enviados.append(json.loads(req.content))
        if falha:
            return httpx.Response(500)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(conteudo)}}]})
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
            return await coro_fn(c)
    return asyncio.run(go()), enviados


def test_triagem_primeira_pergunta_e_fixa_sem_ia():
    r, enviados = rodar(lambda c: ia.triagem(c, []))
    assert r["pergunta"] == ia.PRIMEIRA_PERGUNTA["pergunta"] and r["fonte"] == "fixa" and not r["fim"]
    assert enviados == []


def test_triagem_usa_ia_depois():
    resp = [{"pergunta": ia.PRIMEIRA_PERGUNTA["pergunta"], "resposta": "Natureza"}]
    ia_diz = {"pergunta": "Viaja com pet?", "opcoes": ["Sim", "Não"], "multi": False, "fim": False, "resumo": None}
    r, enviados = rodar(lambda c: ia.triagem(c, resp), ia_diz)
    assert r["pergunta"] == "Viaja com pet?" and r["fonte"] == "ia"
    assert enviados[0]["model"] == ia.MODELO_RACIOCINIO


def test_triagem_termina_na_quinta():
    resp = [{"pergunta": f"p{i}", "resposta": "r"} for i in range(5)]
    ia_diz = {"pergunta": "mais uma?", "opcoes": [], "multi": False, "fim": False, "resumo": "Gosta de natureza."}
    r, _ = rodar(lambda c: ia.triagem(c, resp), ia_diz)
    assert r["fim"] is True and r["pergunta"] is None and r["resumo"] == "Gosta de natureza."


def test_triagem_fallback_usa_reserva():
    resp = [{"pergunta": ia.PRIMEIRA_PERGUNTA["pergunta"], "resposta": "Natureza"}]
    r, _ = rodar(lambda c: ia.triagem(c, resp), falha=True)
    assert r["pergunta"] == ia.PERGUNTAS_RESERVA[0]["pergunta"] and r["fonte"] == "fixa"


def test_triagem_primeira_pergunta_aceita_varias_respostas():
    r, _ = rodar(lambda c: ia.triagem(c, []))
    assert r["multi"] is True and r["livre"] is False


def test_triagem_reserva_diz_se_aceita_varias_respostas():
    resp = [{"pergunta": ia.PRIMEIRA_PERGUNTA["pergunta"], "resposta": "Natureza"}]
    r, _ = rodar(lambda c: ia.triagem(c, resp), falha=True)
    assert r["multi"] is False  # com quem viaja: uma resposta só
    resp.append({"pergunta": r["pergunta"], "resposta": "Casal"})
    r, _ = rodar(lambda c: ia.triagem(c, resp), falha=True)
    assert r["pergunta"] == "Que comida você procura na estrada?" and r["multi"] is True


def test_triagem_ia_diz_se_aceita_varias_respostas():
    resp = [{"pergunta": ia.PRIMEIRA_PERGUNTA["pergunta"], "resposta": "Natureza"}]
    ia_diz = {"pergunta": "O que gosta de comer?", "opcoes": ["Caseira", "Churrasco"], "multi": True,
              "fim": False, "resumo": None}
    r, enviados = rodar(lambda c: ia.triagem(c, resp), ia_diz)
    assert r["multi"] is True and r["livre"] is False
    schema = enviados[0]["response_format"]["json_schema"]["schema"]
    assert "multi" in schema["required"]


def test_triagem_quinta_pergunta_e_livre_com_ou_sem_ia():
    resp = [{"pergunta": ia.PRIMEIRA_PERGUNTA["pergunta"], "resposta": "Natureza"},
            {"pergunta": "Com quem você costuma viajar?", "resposta": "Casal"},
            {"pergunta": "Que comida você procura na estrada?", "resposta": "Churrasco"},
            {"pergunta": "Quanto quer gastar por refeição?", "resposta": "R$ 50 a 100"}]
    r, _ = rodar(lambda c: ia.triagem(c, resp), falha=True)
    assert r["livre"] is True and not r["fim"]
    ia_diz = {"pergunta": "O que não pode faltar?", "opcoes": [], "multi": False, "fim": False, "resumo": None}
    r, _ = rodar(lambda c: ia.triagem(c, resp), ia_diz)
    assert r["livre"] is True and r["pergunta"] == "O que não pode faltar?"


def test_triagem_fim_nao_e_multi_nem_livre():
    resp = [{"pergunta": f"p{i}", "resposta": "r"} for i in range(5)]
    r, _ = rodar(lambda c: ia.triagem(c, resp), falha=True)
    assert r["fim"] is True and r["multi"] is False and r["livre"] is False


def test_ranquear_reordena_os_30_primeiros_e_mantem_o_resto():
    ordem = [f"c{i}" for i in reversed(range(30))]
    r, enviados = rodar(lambda c: ia.ranquear(c, CARDS, "Viaja com pet"), {"ids": ordem})
    assert [c["id"] for c in r[:30]] == ordem
    assert [c["id"] for c in r[30:]] == [f"c{i}" for i in range(30, 35)]
    mandados = json.loads(enviados[0]["messages"][1]["content"])["cards"]
    assert len(mandados) == 30 and len(mandados[0]["descricao"]) <= 120
    assert enviados[0]["model"] == ia.MODELO_RAPIDO


def test_ranquear_ids_estranhos():
    r, _ = rodar(lambda c: ia.ranquear(c, CARDS[:4], "x"), {"ids": ["c2", "zzz", "c2", "c0"]})
    assert [c["id"] for c in r] == ["c2", "c0", "c1", "c3"]


def test_ranquear_fallback():
    r, _ = rodar(lambda c: ia.ranquear(c, CARDS[:3], "x"), falha=True)
    assert [c["id"] for c in r] == ["c0", "c1", "c2"]


def test_ranquear_sem_resumo_nao_chama_ia():
    r, enviados = rodar(lambda c: ia.ranquear(c, CARDS[:3], ""))
    assert enviados == [] and [c["id"] for c in r] == ["c0", "c1", "c2"]


def test_roteiro_ia_e_fallback():
    itens = [CARDS[2], CARDS[0], CARDS[1]]
    ia_diz = {"ordem": [{"id": "c1", "porque": "café"}, {"id": "c0", "porque": "mirante"}]}
    r, _ = rodar(lambda c: ia.ajustar_roteiro(c, itens, {"saida": "07:00"}), ia_diz)
    assert [c["id"] for c in r["itens"]] == ["c1", "c0", "c2"] and r["fonte"] == "ia"
    assert r["explicacoes"] == {"c1": "café", "c0": "mirante"}
    r2, _ = rodar(lambda c: ia.ajustar_roteiro(c, itens, {}), falha=True)
    assert [c["id"] for c in r2["itens"]] == ["c0", "c1", "c2"] and r2["fonte"] == "geometria"


def test_roteiro_manda_a_hora_de_chegada_de_cada_lugar_para_a_ia():
    """Issue #27: com a saída no contexto, a IA recebe a hora de chegada, para pôr o almoço entre 11h e 14h."""
    itens = [{**CARDS[0], "horas_desde_saida": 4.5}, {**CARDS[1], "horas_desde_saida": 18.25}]
    _, enviados = rodar(lambda c: ia.ajustar_roteiro(c, itens, {"saida": "07:00", "dias": 2}), {"ordem": []})
    lugares = json.loads(enviados[0]["messages"][1]["content"])["lugares"]
    # issue #95: 13h45 de estrada depois do almoço não cabem num dia de 9h ao volante. Dorme no
    # primeiro lugar, roda um dia inteiro e chega no terceiro dia, não à 01h15 do segundo
    assert [(l["horas_desde_saida"], l["chegada"], l["dia"], l["pernoite"]) for l in lugares] == [
        (4.5, "11:30", 1, True), (18.25, "11:45", 3, False)]
    assert json.loads(enviados[0]["messages"][1]["content"])["horas_volante_por_dia"] == 9
    assert "chegada" in enviados[0]["messages"][0]["content"]


def test_roteiro_sem_saida_nao_inventa_chegada():
    _, enviados = rodar(lambda c: ia.ajustar_roteiro(c, [{**CARDS[0], "horas_desde_saida": 1.0}], {}), {"ordem": []})
    [lugar] = json.loads(enviados[0]["messages"][1]["content"])["lugares"]
    assert "chegada" not in lugar and lugar["horas_desde_saida"] == 1.0
    for saida in (7, "7h", "24:00"):
        _, enviados = rodar(lambda c: ia.ajustar_roteiro(c, [{**CARDS[0], "horas_desde_saida": 1.0}],
                                                         {"saida": saida}), {"ordem": []})
        assert "chegada" not in json.loads(enviados[0]["messages"][1]["content"])["lugares"][0]


def test_endpoints_sem_chave_funcionam(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from conftest import token
    monkeypatch.delenv("GROQ_API_KEY")
    cli = TestClient(app, headers={"Authorization": f"Bearer {token('00000000-0000-4000-8000-000000000001')}"})
    assert cli.post("/triagem", json={"respostas": []}).json()["fonte"] == "fixa"
    assert [c["id"] for c in cli.post("/cards/ranquear", json={"cards": CARDS[:3], "resumo": "x"}).json()] == ["c0", "c1", "c2"]
    r = cli.post("/roteiro", json={"cards": CARDS[:3], "usar_ia": True}).json()
    assert r["fonte"] == "geometria"


def test_assunto_da_reserva_por_palavra_inteira():
    from app import ia
    assert ia._assuntos(["Vai levar o pet?"]) == {"companhia"}
    assert ia._assuntos(["Gosta de petisco?", "Quer repetir a cidade?"]) == set()
    assert ia._assuntos(["Quanto tempo você tem?"]) == set()
    assert ia._assuntos(["Quanto quer gastar por dia?"]) == {"orcamento"}
