"""Cache da coleta no Postgres (tabela `cache`), com validade (30 dias por padrão) e compartilhado entre usuários.

Guarda o que é caro e muda pouco: lugares do OpenStreetMap e do Google Maps por
(cidade, UF, categoria), geocodificação do Nominatim, cidades no caminho e rotas
do OSRM. É o que leva o primeiro card a menos de 60 s quando a rota já foi feita.

Um erro no cache (ou banco não configurado) nunca derruba a coleta: vira um
"não tinha" e segue para a fonte.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import banco

log = logging.getLogger("desvio.cache")
DIAS = float(os.getenv("PV_CACHE_DIAS", "30"))
_ERROS = psycopg.Error


def obter(chave: str, dias: float | None = None) -> Any | None:
    """O valor guardado há menos de `dias` (padrão PV_CACHE_DIAS), ou None."""
    if not banco.URL:  # sem banco (CLI, testes): sem cache, sem aviso
        return None
    try:
        with banco.conectar() as con:
            l = con.execute("select valor from cache where chave = %s "
                            "and guardado_em > now() - make_interval(secs => %s)",
                            (chave, (DIAS if dias is None else dias) * 86400)).fetchone()
    except _ERROS:
        log.warning("cache indisponível ao ler %s", chave, exc_info=True)
        return None
    return l["valor"] if l else None


def guardar(chave: str, valor: Any) -> None:
    if not banco.URL:
        return
    try:
        with banco.conectar() as con:
            con.execute("insert into cache (chave, valor) values (%s, %s) "
                        "on conflict (chave) do update set valor = excluded.valor, guardado_em = now()",
                        (chave, Jsonb(valor)))
    except _ERROS:
        log.warning("cache indisponível ao gravar %s", chave, exc_info=True)


def apagar_vencidos(dias: float | None = None) -> int:
    """Limpa o que passou da validade (para rodar de vez em quando no worker)."""
    with banco.conectar() as con:
        cur = con.execute("delete from cache where guardado_em <= now() - make_interval(secs => %s)",
                          ((DIAS if dias is None else dias) * 86400,))
    return cur.rowcount
