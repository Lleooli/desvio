"""Aviso push quando a busca termina (HU07).

O app manda o token do Expo (`ExponentPushToken[...]` ou `ExpoPushToken[...]`).
O worker, depois de marcar o job como pronto, pede o envio à API do Expo. Rede,
token inválido ou aparelho desregistrado só vão para o log: a busca já acabou.
"""
from __future__ import annotations

import logging
import re

import httpx

from . import banco

log = logging.getLogger("desvio.push")

URL_EXPO = "https://exp.host/--/api/v2/push/send"
TOKEN = re.compile(r"^(Exponent|Expo)PushToken\[[A-Za-z0-9_-]{8,200}\]$")
_transporte: httpx.BaseTransport | None = None  # os testes trocam por um httpx.MockTransport


def guardar_token(usuario: str, token: str | None) -> None:
    """Grava o token deste aparelho, ou tira (None) quando a pessoa sai ou desliga o aviso."""
    if token is not None:
        token = token.strip() or None
    if token is not None and not TOKEN.fullmatch(token):
        raise ValueError("Token de push inválido")
    with banco.conectar() as con:
        banco.garantir_usuario(usuario, con=con)
        con.execute("update usuario set expo_push_token = %s where id = %s", (token, usuario))


def _cidade(destino: str | None) -> str:
    """Vitória da Conquista, BA vira Vitória da Conquista, como a pessoa reconhece o lugar."""
    if not destino:
        return ""
    return str(destino).split(",")[0].strip()


async def avisar_busca_pronta(job: dict) -> None:
    """Manda o push da busca pronta. Sem token, ou se o Expo falhar, não faz nada além do log."""
    entrada = job.get("entrada") or {}
    usuario, viagem = entrada.get("usuario"), entrada.get("viagem")
    if not usuario or not viagem:
        return
    try:
        with banco.conectar() as con:
            linha = con.execute("select expo_push_token from usuario where id = %s", (usuario,)).fetchone()
        token = linha["expo_push_token"] if linha else None
        if not token:
            return
        cidade = _cidade(entrada.get("destino"))
        corpo = f"Suas paradas para {cidade} estão prontas" if cidade else "Suas paradas estão prontas"
        async with httpx.AsyncClient(transport=_transporte, timeout=10) as client:
            r = await client.post(URL_EXPO, json={
                "to": token,
                "title": "Paradas prontas",
                "body": corpo,
                "data": {"viagem_id": str(viagem), "job_id": job["id"], "rota": f"/viagens/{viagem}/paradas"},
                "channelId": "busca",
            }, headers={"Accept": "application/json"})
            r.raise_for_status()
            detalhe = r.json().get("data") if r.headers.get("content-type", "").startswith("application/json") else None
            if isinstance(detalhe, dict) and detalhe.get("status") == "error":
                log.warning("Expo Push recusou o aviso do job %s: %s", job["id"], detalhe.get("message"))
    except Exception:
        log.warning("não consegui avisar que a busca %s terminou", job.get("id"), exc_info=True)
