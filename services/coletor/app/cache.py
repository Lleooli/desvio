"""Cache da coleta no Postgres (tabela `cache`), com validade (30 dias por padrão) e compartilhado entre usuários.

Guarda o que é caro e muda pouco: lugares do OpenStreetMap e do Google Maps por
(cidade, UF, categoria), geocodificação do Nominatim, cidades no caminho e rotas
do OSRM. É o que leva o primeiro card a menos de 60 s quando a rota já foi feita.

Um erro no cache (ou banco não configurado) nunca derruba a coleta: vira um
"não tinha" e segue para a fonte.

Uma conexão só por job (#62): a primeira chamada conecta e as outras
reaproveitam; `sessao()` (aberta em coletor.planejar_viagem) fecha no fim. Se a
conexão falha, o cache fica desligado até o fim do job, sem tentar de novo a
cada parada × categoria (cada tentativa travaria o event loop até 5 s). O
worker roda um job por vez, então o estado fica no módulo.
"""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import banco

log = logging.getLogger("desvio.cache")
DIAS = float(os.getenv("PV_CACHE_DIAS", "30"))
_ERROS = psycopg.Error

_con: psycopg.Connection | None = None
_desligado = False  # a conexão falhou neste job: segue sem cache até o fim dele


def _fechar() -> None:
    global _con
    if _con is not None:
        try:
            _con.close()
        except _ERROS:
            pass
    _con = None


@asynccontextmanager
async def sessao() -> AsyncIterator[None]:
    """Um job da coleta: no fim fecha a conexão e religa o cache para o próximo."""
    global _desligado
    try:
        yield
    finally:
        _fechar()
        _desligado = False


def _conexao() -> psycopg.Connection | None:
    """A conexão do job (autocommit: cada leitura e gravação vale sozinha), ou None."""
    global _con
    if not banco.URL or _desligado:  # sem banco (CLI, testes): sem cache, sem aviso
        return None
    if _con is None or _con.closed:
        try:
            _con = banco.conectar(autocommit=True)
        except _ERROS:
            _desligar("conectar")
            return None
    return _con


def _desligar(ao: str) -> None:
    global _desligado
    log.warning("cache indisponível ao %s; sigo sem cache até o fim do job", ao, exc_info=True)
    _desligado = True
    _fechar()


def obter(chave: str, dias: float | None = None) -> Any | None:
    """O valor guardado há menos de `dias` (padrão PV_CACHE_DIAS), ou None."""
    con = _conexao()
    if con is None:
        return None
    try:
        l = con.execute("select valor from cache where chave = %s "
                        "and guardado_em > now() - make_interval(secs => %s)",
                        (chave, (DIAS if dias is None else dias) * 86400)).fetchone()
    except _ERROS:
        _desligar(f"ler {chave}")
        return None
    return l["valor"] if l else None


def guardar(chave: str, valor: Any) -> None:
    con = _conexao()
    if con is None:
        return
    try:
        con.execute("insert into cache (chave, valor) values (%s, %s) "
                    "on conflict (chave) do update set valor = excluded.valor, guardado_em = now()",
                    (chave, Jsonb(valor)))
    except _ERROS:
        _desligar(f"gravar {chave}")


def apagar_vencidos(dias: float | None = None) -> int:
    """Limpa o que passou da validade (para rodar de vez em quando no worker)."""
    with banco.conectar() as con:
        cur = con.execute("delete from cache where guardado_em <= now() - make_interval(secs => %s)",
                          ((DIAS if dias is None else dias) * 86400,))
    return cur.rowcount
