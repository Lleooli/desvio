import asyncio
import json

import httpx
import pytest

from app import ia

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
          "required": ["ok"], "additionalProperties": False}


def cliente(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def resposta(conteudo: str, status=200, headers=None):
    return httpx.Response(status, headers=headers,
                          json={"choices": [{"message": {"content": conteudo}}]} if status == 200 else {"error": {}})


@pytest.fixture(autouse=True)
def chave(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "teste")
    ia._limitadores.clear()


def chamar(handler, **kw):
    async def go():
        async with cliente(handler) as c:
            return await ia.chamar_json(c, modelo="m", sistema="s", dados={"x": 1},
                                        schema=SCHEMA, nome="t", **kw)
    return asyncio.run(go())


def test_chamada_ok_manda_schema_estrito():
    visto = {}
    def h(req):
        visto.update(json.loads(req.content))
        visto["auth"] = req.headers["authorization"]
        return resposta('{"ok": true}')
    assert chamar(h) == {"ok": True}
    assert visto["auth"] == "Bearer teste"
    assert visto["response_format"]["json_schema"]["strict"] is True
    assert visto["response_format"]["json_schema"]["schema"] == SCHEMA
    assert visto["reasoning_effort"] == "low"
    assert json.loads(visto["messages"][1]["content"]) == {"x": 1}


def test_ia_sem_chave(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    with pytest.raises(ia.IAIndisponivel, match="GROQ_API_KEY"):
        chamar(lambda req: resposta('{"ok": true}'))


def test_429_vira_indisponivel():
    with pytest.raises(ia.IAIndisponivel, match="429"):
        chamar(lambda req: resposta("", status=429, headers={"retry-after": "7"}))


def test_json_invalido_vira_indisponivel():
    with pytest.raises(ia.IAIndisponivel):
        chamar(lambda req: resposta("isto não é json"))


def test_timeout_vira_indisponivel():
    def h(req):
        raise httpx.ReadTimeout("lento", request=req)
    with pytest.raises(ia.IAIndisponivel):
        chamar(h)


def test_limitador_por_tokens_e_requisicoes():
    agora = [100.0]
    lim = ia.Limitador(rpm=2, tpm=1000, relogio=lambda: agora[0])
    assert lim.espera(600) == 0
    lim.registrar(600)
    assert lim.espera(600) == pytest.approx(60.0)   # passaria de 1000 tokens no minuto
    assert lim.espera(300) == 0
    lim.registrar(300)
    assert lim.espera(10) == pytest.approx(60.0)    # já são 2 requisições no minuto
    agora[0] += 61
    assert lim.espera(600) == 0


def test_limitador_cheio_nao_espera_mais_que_o_timeout():
    ia._limitadores["m"] = ia.Limitador(rpm=1, tpm=8000)
    ia._limitadores["m"].registrar(10)
    with pytest.raises(ia.IAIndisponivel, match="limite"):
        chamar(lambda req: resposta('{"ok": true}'))
