"""Cache da coleta em SQLite, com validade (30 dias por padrão) e compartilhado entre usuários.

Guarda o que é caro e muda pouco: lugares do OpenStreetMap e do Google Maps por
(cidade, UF, categoria), geocodificação do Nominatim, cidades no caminho e rotas
do OSRM. É o que leva o primeiro card a menos de 60 s quando a rota já foi feita.

Um erro no cache nunca derruba a coleta: vira um "não tinha" e segue para a fonte.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import closing
from typing import Any

log = logging.getLogger("desvio.cache")
DB = os.getenv("PV_DB", "planejador.db")
DIAS = float(os.getenv("PV_CACHE_DIAS", "30"))


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(DB, timeout=30)
    con.execute("""CREATE TABLE IF NOT EXISTS cache (
        chave TEXT PRIMARY KEY, valor TEXT NOT NULL,
        guardado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')))""")
    return con


def obter(chave: str, dias: float | None = None) -> Any | None:
    """O valor guardado há menos de `dias` (padrão PV_CACHE_DIAS), ou None."""
    try:
        with closing(_con()) as con:
            l = con.execute("SELECT valor FROM cache WHERE chave=? AND julianday('now') - julianday(guardado_em) < ?",
                            (chave, DIAS if dias is None else dias)).fetchone()
    except sqlite3.Error:
        log.warning("cache indisponível ao ler %s", chave, exc_info=True)
        return None
    return json.loads(l[0]) if l else None


def guardar(chave: str, valor: Any) -> None:
    try:
        with closing(_con()) as con, con:
            con.execute("INSERT OR REPLACE INTO cache (chave, valor) VALUES (?, ?)",
                        (chave, json.dumps(valor, ensure_ascii=False)))
    except sqlite3.Error:
        log.warning("cache indisponível ao gravar %s", chave, exc_info=True)


def apagar_vencidos(dias: float | None = None) -> int:
    """Limpa o que passou da validade (para rodar de vez em quando no worker)."""
    with closing(_con()) as con, con:
        cur = con.execute("DELETE FROM cache WHERE julianday('now') - julianday(guardado_em) >= ?",
                          (DIAS if dias is None else dias,))
    return cur.rowcount
