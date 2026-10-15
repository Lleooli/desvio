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
    ia_diz = {"pergunta": "Viaja com pet?", "opcoes": ["Sim", "Não"], "fim": False, "resumo": None}
    r, enviados = rodar(lambda c: ia.triagem(c, resp), ia_diz)
    assert r["pergunta"] == "Viaja com pet?" and r["fonte"] == "ia"
    assert enviados[0]["model"] == ia.MODELO_RACIOCINIO


def test_triagem_termina_na_quinta():
    resp = [{"pergunta": f"p{i}", "resposta": "r"} for i in range(5)]
    ia_diz = {"pergunta": "mais uma?", "opcoes": [], "fim": False, "resumo": "Gosta de natureza."}
    r, _ = rodar(lambda c: ia.triagem(c, resp), ia_diz)
    assert r["fim"] is True and r["pergunta"] is None and r["resumo"] == "Gosta de natureza."


def test_triagem_fallback_usa_reserva():
    resp = [{"pergunta": ia.PRIMEIRA_PERGUNTA["pergunta"], "resposta": "Natureza"}]
    r, _ = rodar(lambda c: ia.triagem(c, resp), falha=True)
    assert r["pergunta"] == ia.PERGUNTAS_RESERVA[0]["pergunta"] and r["fonte"] == "fixa"


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
    ia_diz = {"ordem": [{"id": "c1", "porque": "almoço"}, {"id": "c0", "porque": "café"}]}
    r, _ = rodar(lambda c: ia.ajustar_roteiro(c, itens, {"saida": "07:00"}), ia_diz)
    assert [c["id"] for c in r["itens"]] == ["c1", "c0", "c2"] and r["fonte"] == "ia"
    assert r["explicacoes"] == {"c1": "almoço", "c0": "café"}
    r2, _ = rodar(lambda c: ia.ajustar_roteiro(c, itens, {}), falha=True)
    assert [c["id"] for c in r2["itens"]] == ["c0", "c1", "c2"] and r2["fonte"] == "geometria"


def test_endpoints_sem_chave_funcionam(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.delenv("GROQ_API_KEY")
    cli = TestClient(app)
    assert cli.post("/triagem", json={"respostas": []}).json()["fonte"] == "fixa"
    assert [c["id"] for c in cli.post("/cards/ranquear", json={"cards": CARDS[:3], "resumo": "x"}).json()] == ["c0", "c1", "c2"]
    r = cli.post("/roteiro/carro", json={"cards": CARDS[:3], "usar_ia": True}).json()
    assert r["fonte"] == "geometria"
