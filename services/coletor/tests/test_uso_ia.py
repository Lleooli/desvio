"""Issue #41: uso do Groq por modelo e por dia, alerta de 80% e consulta."""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ia, uso_ia
from app.main import app

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
          "required": ["ok"], "additionalProperties": False}


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(uso_ia, "DB", str(tmp_path / "uso.db"))
    monkeypatch.setenv("GROQ_API_KEY", "teste")
    ia._limitadores.clear()


def chamar(resposta, modelo="m"):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: resposta)) as c:
            return await ia.chamar_json(c, modelo=modelo, sistema="s", dados={}, schema=SCHEMA, nome="t")
    return asyncio.run(go())


def ok(usage=None):
    corpo = {"choices": [{"message": {"content": '{"ok": true}'}}]}
    if usage is not None:
        corpo["usage"] = usage
    return httpx.Response(200, json=corpo)


def test_soma_chamadas_e_tokens_por_modelo_e_dia():
    chamar(ok({"total_tokens": 300}), "a")
    chamar(ok({"total_tokens": 200}), "a")
    chamar(ok({"total_tokens": 50}), "b")
    r = {l["modelo"]: l for l in uso_ia.resumo()}
    assert r["a"]["chamadas"] == 2 and r["a"]["tokens"] == 500
    assert r["b"]["chamadas"] == 1 and r["b"]["tokens"] == 50
    assert r["a"]["cota_tokens"] == pytest.approx(500 / 200000, abs=1e-3)


def test_sem_usage_usa_a_estimativa():
    chamar(ok())
    assert uso_ia.resumo()[0]["tokens"] > 0


def test_erro_do_groq_nao_conta():
    with pytest.raises(ia.IAIndisponivel):
        chamar(httpx.Response(500))
    assert uso_ia.resumo() == []


def test_alerta_uma_vez_ao_passar_de_80_por_cento(monkeypatch, caplog):
    monkeypatch.setattr(uso_ia, "COTA_REQUISICOES_DIA", 10)
    for _ in range(7):
        uso_ia.registrar("m", 10)
    assert "ALERTA" not in caplog.text
    uso_ia.registrar("m", 10)  # 8 de 10
    assert caplog.text.count("ALERTA cota do Groq") == 1
    uso_ia.registrar("m", 10)
    assert caplog.text.count("ALERTA cota do Groq") == 1


def test_alerta_por_tokens(monkeypatch, caplog):
    monkeypatch.setattr(uso_ia, "COTA_TOKENS_DIA", 1000)
    uso_ia.registrar("m", 850)
    assert "ALERTA cota do Groq: m" in caplog.text


def test_banco_quebrado_nao_derruba_a_ia(monkeypatch, tmp_path):
    monkeypatch.setattr(uso_ia, "DB", str(tmp_path))  # pasta: o SQLite não abre
    assert chamar(ok({"total_tokens": 10})) == {"ok": True}


def test_consulta_exige_token_de_admin(monkeypatch):
    api = TestClient(app)
    uso_ia.registrar("m", 100)
    monkeypatch.delenv("PV_ADMIN_TOKEN", raising=False)
    assert api.get("/uso/ia").status_code == 404
    monkeypatch.setenv("PV_ADMIN_TOKEN", "segredo")
    assert api.get("/uso/ia").status_code == 404
    assert api.get("/uso/ia", headers={"x-admin-token": "errado"}).status_code == 404
    r = api.get("/uso/ia", headers={"x-admin-token": "segredo"})
    assert r.status_code == 200
    assert r.json()["dias"][0]["modelo"] == "m" and r.json()["cota_tokens_dia"] == 200000
    assert "/uso/ia" not in json.dumps(api.get("/openapi.json").json())
