"""Uso do Groq por modelo e por dia, com alerta ao passar de 80% da cota diária.

O plano gratuito tem, por modelo e por organização, 1.000 requisições e 200 mil
tokens por dia. Cada chamada que chega ao Groq é somada aqui (tokens da resposta
em `usage`, ou a estimativa quando ela não vem). A primeira chamada do dia que
passa de 80% de qualquer um dos dois limites gera um aviso no log, uma vez por
modelo e por dia. A consulta fica em GET /uso/ia (ver main.py).
"""
from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing

log = logging.getLogger("desvio.uso_ia")
DB = os.getenv("PV_DB", "planejador.db")
COTA_REQUISICOES_DIA = int(os.getenv("PV_GROQ_COTA_REQ_DIA", "1000"))
COTA_TOKENS_DIA = int(os.getenv("PV_GROQ_COTA_TOKENS_DIA", "200000"))
ALERTA = 0.8


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(DB, timeout=30)
    con.execute("""CREATE TABLE IF NOT EXISTS uso_ia (
        dia TEXT NOT NULL, modelo TEXT NOT NULL,
        chamadas INTEGER NOT NULL DEFAULT 0, tokens INTEGER NOT NULL DEFAULT 0,
        alertado INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (dia, modelo))""")
    return con


def registrar(modelo: str, tokens: int) -> None:
    """Soma uma chamada; nunca levanta (contar uso não pode derrubar a IA)."""
    try:
        with closing(_con()) as con, con:
            con.execute("INSERT INTO uso_ia (dia, modelo, chamadas, tokens) VALUES (date('now'), ?, 1, ?) "
                        "ON CONFLICT (dia, modelo) DO UPDATE SET chamadas = chamadas + 1, "
                        "tokens = tokens + excluded.tokens", (modelo, tokens))
            chamadas, total, alertado = con.execute(
                "SELECT chamadas, tokens, alertado FROM uso_ia WHERE dia = date('now') AND modelo = ?",
                (modelo,)).fetchone()
            if not alertado and (chamadas >= ALERTA * COTA_REQUISICOES_DIA or total >= ALERTA * COTA_TOKENS_DIA):
                con.execute("UPDATE uso_ia SET alertado = 1 WHERE dia = date('now') AND modelo = ?", (modelo,))
                log.warning("ALERTA cota do Groq: %s passou de 80%% hoje (%d de %d requisições, %d de %d tokens)",
                            modelo, chamadas, COTA_REQUISICOES_DIA, total, COTA_TOKENS_DIA)
    except sqlite3.Error:
        log.warning("não consegui registrar o uso do Groq", exc_info=True)


def resumo(dias: int = 7) -> list[dict]:
    """Uso diário por modelo nos últimos `dias`, com a fração da cota usada."""
    with closing(_con()) as con:
        linhas = con.execute("SELECT dia, modelo, chamadas, tokens FROM uso_ia "
                             "WHERE dia > date('now', ?) ORDER BY dia DESC, modelo",
                             (f"-{int(dias)} days",)).fetchall()
    return [{"dia": d, "modelo": m, "chamadas": c, "tokens": t,
             "cota_requisicoes": round(c / COTA_REQUISICOES_DIA, 3),
             "cota_tokens": round(t / COTA_TOKENS_DIA, 3)} for d, m, c, t in linhas]
