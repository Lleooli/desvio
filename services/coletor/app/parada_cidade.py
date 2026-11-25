"""Cidades já coletadas, compartilhadas entre todas as pessoas (tabela `parada_cidade`, #93).

Cada linha guarda os cards de uma cidade (OpenStreetMap, Google e Instagram) e a ordem
genérica da IA, feita sem o gosto de ninguém. Uma viagem que passa por uma cidade já
feita há menos de 30 dias usa a linha e não chama Overpass, Google, Instagram nem Groq.
O gosto de cada pessoa entra depois, sem IA (preferencias.personalizar).

A chave é (cidade, categorias, variante):
- cidade: o código IBGE ("ibge:4300406") quando nome e UF batem com a lista do IBGE;
  senão "nome:<nome normalizado>|<UF>", o que o coletor já usa nas outras chaves.
- categorias: ordenadas, separadas por vírgula.
- variante: raio da busca, cards por categoria e fonte ("osm" ou "google"); mudam os
  cards, então uma linha feita com outro raio ou sem o Google não responde pela outra.

Usa a conexão do job (cache.consultar): erro de banco vira "não tem" e a coleta segue.
"""
from __future__ import annotations

import re
import unicodedata

from psycopg.types.json import Jsonb

from . import cache, cidades

# Linha com busca do Google vazia (o gosom pode não ter alcançado a cidade) vale só 1 dia
DIAS_INCOMPLETA = 1
_VALIDA = ("atualizado_em > now() - make_interval(secs => case when completa then %s else %s end)")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def id_cidade(nome: str, uf: str | None) -> str:
    local = cidades.exata(f"{nome}, {uf}") if uf else None
    if local and local.get("codigo_ibge"):
        return "ibge:" + local["codigo_ibge"]
    return f"nome:{_norm(nome)}|{uf or ''}"


def texto_categorias(categorias: list[str]) -> str:
    return ",".join(sorted(set(categorias)))


def variante(raio_km: float, por_categoria: int, usar_google_maps: bool) -> str:
    return f"r{float(raio_km):g}|n{por_categoria}|{'google' if usar_google_maps else 'osm'}"


def _validade() -> tuple[float, float]:
    return cache.DIAS * 86400, DIAS_INCOMPLETA * 86400


def proximas(categorias: str, var: str, sul: float, oeste: float, norte: float, leste: float) -> list[dict]:
    """Cidades válidas dentro do retângulo, sem os cards (para escolher as paradas)."""
    linhas = cache.consultar(
        "select cidade, nome, uf, lat, lon from parada_cidade "
        f"where categorias = %s and variante = %s and lat between %s and %s and lon between %s and %s and {_VALIDA}",
        (categorias, var, sul, norte, oeste, leste, *_validade()), ao="ler parada_cidade")
    return linhas or []


def obter(cidade: str, categorias: str, var: str) -> dict | None:
    """A linha válida da cidade (cards e ordem da IA), ou None."""
    linhas = cache.consultar(
        "select cidade, nome, uf, lat, lon, cards, ordem_ia, completa from parada_cidade "
        f"where cidade = %s and categorias = %s and variante = %s and {_VALIDA}",
        (cidade, categorias, var, *_validade()), ao="ler parada_cidade")
    return linhas[0] if linhas else None


def guardar(cidade: str, categorias: str, var: str, parada: dict, cards: list[dict],
            ordem_ia: list[str] | None, completa: bool) -> None:
    cache.consultar(
        "insert into parada_cidade (cidade, categorias, variante, nome, uf, lat, lon, cards, ordem_ia, completa) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "on conflict (cidade, categorias, variante) do update set nome = excluded.nome, uf = excluded.uf, "
        "lat = excluded.lat, lon = excluded.lon, cards = excluded.cards, ordem_ia = excluded.ordem_ia, "
        "completa = excluded.completa, atualizado_em = now()",
        (cidade, categorias, var, parada["nome"], parada.get("uf"), parada["lat"], parada["lon"],
         Jsonb(cards), Jsonb(ordem_ia) if ordem_ia is not None else None, completa),
        ao="gravar parada_cidade")
