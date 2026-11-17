"""Uso do Groq por modelo e por dia, com alerta ao passar de 80% da cota diária.

O plano gratuito tem, por modelo e por organização, 1.000 requisições e 200 mil
tokens por dia. Cada chamada que chega ao Groq é somada aqui (tokens da resposta
em `usage`, ou a estimativa quando ela não vem). A primeira chamada do dia que
passa de 80% de qualquer um dos dois limites gera um aviso no log, uma vez por
modelo e por dia. A consulta fica em GET /uso/ia (ver main.py).

A tabela `uso_ia` fica no Postgres (app/banco.py), assim a API e o worker somam no
mesmo lugar. O dia é o de UTC.
"""
from __future__ import annotations

import logging
import os

from . import banco

log = logging.getLogger("desvio.uso_ia")
COTA_REQUISICOES_DIA = int(os.getenv("PV_GROQ_COTA_REQ_DIA", "1000"))
COTA_TOKENS_DIA = int(os.getenv("PV_GROQ_COTA_TOKENS_DIA", "200000"))
ALERTA = 0.8
_HOJE = "(now() at time zone 'utc')::date"


def registrar(modelo: str, tokens: int) -> None:
    """Soma uma chamada; nunca levanta (contar uso não pode derrubar a IA)."""
    try:
        with banco.conectar() as con:
            chamadas, total, alertado = con.execute(
                f"insert into uso_ia (dia, modelo, chamadas, tokens) values ({_HOJE}, %s, 1, %s) "
                "on conflict (dia, modelo) do update set chamadas = uso_ia.chamadas + 1, "
                "tokens = uso_ia.tokens + excluded.tokens "
                "returning chamadas, tokens, alertado", (modelo, tokens)).fetchone().values()
            if not alertado and (chamadas >= ALERTA * COTA_REQUISICOES_DIA or total >= ALERTA * COTA_TOKENS_DIA):
                con.execute(f"update uso_ia set alertado = true where dia = {_HOJE} and modelo = %s", (modelo,))
                log.warning("ALERTA cota do Groq: %s passou de 80%% hoje (%d de %d requisições, %d de %d tokens)",
                            modelo, chamadas, COTA_REQUISICOES_DIA, total, COTA_TOKENS_DIA)
    except Exception:  # banco fora, sem PV_DATABASE_URL etc.
        log.warning("não consegui registrar o uso do Groq", exc_info=True)


def resumo(dias: int = 7) -> list[dict]:
    """Uso diário por modelo nos últimos `dias`, com a fração da cota usada."""
    with banco.conectar() as con:
        linhas = con.execute(f"select dia, modelo, chamadas, tokens from uso_ia "
                             f"where dia > {_HOJE} - %s order by dia desc, modelo", (int(dias),)).fetchall()
    return [{"dia": l["dia"].isoformat(), "modelo": l["modelo"], "chamadas": l["chamadas"], "tokens": l["tokens"],
             "cota_requisicoes": round(l["chamadas"] / COTA_REQUISICOES_DIA, 3),
             "cota_tokens": round(l["tokens"] / COTA_TOKENS_DIA, 3)} for l in linhas]
