"""Issue #34: limitador com lock, prazo total de 10 s e triagem de reserva melhor."""
import asyncio
import json
import time

import httpx
import pytest

from app import ia

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
          "required": ["ok"], "additionalProperties": False}


@pytest.fixture(autouse=True)
def chave(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "teste")
    ia._limitadores.clear()


def _ok(req=None):
    return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})


# --- Limitador com lock --------------------------------------------------------

def test_10_reservas_simultaneas_nao_estouram_o_limite():
    agora = [0.0]

    async def dormir(s):
        await asyncio.sleep(0)  # deixa as outras corrotinas rodarem no meio da espera
        agora[0] += s

    lim = ia.Limitador(rpm=3, tpm=8000, relogio=lambda: agora[0], dormir=dormir)
    momentos = []

    async def uma():
        await lim.reservar(10, prazo_s=float("inf"))
        momentos.append(agora[0])

    async def go():
        await asyncio.gather(*(uma() for _ in range(10)))
    asyncio.run(go())

    assert len(momentos) == 10
    for t in momentos:  # em nenhuma janela de 60 s passam mais de 3
        assert sum(1 for x in momentos if t <= x < t + 60) <= 3


def test_reserva_que_passa_do_prazo_vira_indisponivel():
    agora = [0.0]
    lim = ia.Limitador(rpm=1, tpm=8000, relogio=lambda: agora[0])
    lim.registrar(10)
    with pytest.raises(ia.IAIndisponivel, match="limite"):
        asyncio.run(lim.reservar(10, prazo_s=10))


def test_chamadas_simultaneas_no_groq_respeitam_o_rpm():
    ia._limitadores["m"] = ia.Limitador(rpm=3, tpm=8000)
    enviados = []

    def h(req):
        enviados.append(1)
        return _ok()

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
            return await asyncio.gather(*(ia.chamar_json(c, modelo="m", sistema="s", dados={}, schema=SCHEMA,
                                                          nome="t", timeout=0.2) for _ in range(10)),
                                        return_exceptions=True)
    r = asyncio.run(go())
    assert len(enviados) == 3  # as outras 7 caem no plano B em vez de tomar 429
    assert sum(isinstance(x, ia.IAIndisponivel) for x in r) == 7


# --- Prazo total ---------------------------------------------------------------

def test_prazo_total_soma_espera_do_limitador_e_http():
    lim = ia._limitadores["m"] = ia.Limitador(rpm=1, tpm=8000)
    lim.registrar(10)
    lim._uso[0] = (time.monotonic() - 59.7, 10)  # libera em uns 0,3 s

    async def h(req):
        await asyncio.sleep(0.4)  # sozinho cabe em 0,5 s; somado à espera, não
        return _ok()

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
            return await ia.chamar_json(c, modelo="m", sistema="s", dados={}, schema=SCHEMA,
                                        nome="t", timeout=0.5)
    inicio = time.monotonic()
    with pytest.raises(ia.IAIndisponivel, match="prazo"):
        asyncio.run(go())
    assert time.monotonic() - inicio < 0.7


def test_http_lento_respeita_o_prazo_mesmo_sem_timeout_do_transporte():
    async def h(req):
        await asyncio.sleep(1)
        return _ok()

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
            return await ia.chamar_json(c, modelo="m", sistema="s", dados={}, schema=SCHEMA,
                                        nome="t", timeout=0.2)
    with pytest.raises(ia.IAIndisponivel, match="prazo"):
        asyncio.run(go())


# --- Triagem de reserva --------------------------------------------------------

def _triagem_sem_ia(respostas):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as c:
            return await ia.triagem(c, respostas)
    return asyncio.run(go())


def test_reserva_nao_repete_assunto_ja_perguntado_pela_ia():
    resp = [{"pergunta": ia.PRIMEIRA_PERGUNTA["pergunta"], "resposta": "Natureza"},
            {"pergunta": "Que tipo de comida você mais curte?", "resposta": "Caseira"}]
    r = _triagem_sem_ia(resp)
    assert r["fonte"] == "fixa" and not r["fim"]
    assert r["pergunta"] == "Com quem você costuma viajar?"  # a de comida já foi feita pela IA
    resp.append({"pergunta": r["pergunta"], "resposta": "Casal"})
    assert _triagem_sem_ia(resp)["pergunta"] == "Quanto quer gastar por refeição?"


def test_reserva_pula_todos_os_assuntos_ja_cobertos():
    resp = [{"pergunta": ia.PRIMEIRA_PERGUNTA["pergunta"], "resposta": "Comida boa"},
            {"pergunta": "Viaja com quem?", "resposta": "Amigos"},
            {"pergunta": "Qual tipo de culinária você curte?", "resposta": "Caseira"},
            {"pergunta": "Quanto pretende gastar?", "resposta": "R$ 50 a 100"}]
    r = _triagem_sem_ia(resp)
    assert r["pergunta"] == "Prefere lugares famosos ou escondidos?"


def test_reserva_sem_pergunta_nova_termina_com_resumo_das_respostas():
    resp = [{"pergunta": ia.PRIMEIRA_PERGUNTA["pergunta"], "resposta": "Natureza"},
            {"pergunta": "Com quem você costuma viajar?", "resposta": "Casal"},
            {"pergunta": "Que comida você procura na estrada?", "resposta": "Churrasco"},
            {"pergunta": "Quanto quer gastar por refeição?", "resposta": "R$ 50 a 100"}]
    r = _triagem_sem_ia(resp + [{"pergunta": "Prefere lugares famosos ou escondidos?", "resposta": "Escondidos"}])
    assert r["fim"] is True and r["pergunta"] is None
    for trecho in ("Natureza", "Casal", "Churrasco", "R$ 50 a 100", "Escondidos"):
        assert trecho in r["resumo"]


def test_fim_da_ia_sem_resumo_ganha_resumo_simples():
    resp = [{"pergunta": f"p{i}?", "resposta": f"r{i}"} for i in range(5)]

    def h(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(
            {"pergunta": None, "opcoes": [], "multi": False, "fim": True, "resumo": None})}}]})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
            return await ia.triagem(c, resp)
    r = asyncio.run(go())
    assert r["fim"] is True and "r4" in r["resumo"]
