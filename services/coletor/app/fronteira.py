"""Se um ponto fica no Brasil, pelo contorno do país, sem internet (issue #95).

O contorno (app/referencia/brasil.json) é o do Natural Earth 1:50m, de domínio público,
com uns 2 km de erro. Por isso `no_brasil` aceita, por padrão, ponto fora do desenho
mas a até MARGEM_KM da fronteira: rio de divisa, cidade gêmea e ilha costeira não
viram "fora do Brasil" por erro do contorno. Um desvio de verdade pelo Paraguai ou
pela Argentina (Hohenau, Misiones) passa dezenas de km da fronteira e é pego.

Serve para checar a rota inteira (geo.rota) e para escolher um ponto de passagem no
Brasil quando nenhuma rota do OSRM fica dentro do país.
"""
from __future__ import annotations

import functools
import json
import math
from pathlib import Path

from . import cidades

ARQUIVO = Path(__file__).parent / "referencia" / "brasil.json"
MARGEM_KM = 15.0
PASSO_KM = 10.0  # de quanto em quanto km a rota é checada
# ponto de passagem: sede de município a pelo menos esta distância da fronteira, para a
# rota até ele não encostar de novo no país vizinho
FOLGA_PASSAGEM_KM = 50.0

Ponto = tuple[float, float]  # (lat, lon)


@functools.cache
def _aneis() -> list[tuple[tuple[float, float, float, float], list[Ponto]]]:
    """Cada anel com a sua caixa (lat mín, lat máx, lon mín, lon máx)."""
    with open(ARQUIVO, encoding="utf-8") as f:
        dados = json.load(f)
    saida = []
    for anel in dados["aneis"]:
        pontos = [(la, lo) for la, lo in anel]
        las, los = [p[0] for p in pontos], [p[1] for p in pontos]
        saida.append(((min(las), max(las), min(los), max(los)), pontos))
    return saida


def _dentro_do_anel(p: Ponto, anel: list[Ponto]) -> bool:
    """Raio para o leste (par/ímpar), em graus: basta para um contorno desta escala."""
    la, lo = p
    dentro = False
    j = len(anel) - 1
    for i in range(len(anel)):
        (la1, lo1), (la2, lo2) = anel[i], anel[j]
        if (la1 > la) != (la2 > la) and lo < (lo2 - lo1) * (la - la1) / (la2 - la1) + lo1:
            dentro = not dentro
        j = i
    return dentro


def _dentro_do_contorno(p: Ponto) -> bool:
    return any(c[0] <= p[0] <= c[1] and c[2] <= p[1] <= c[3] and _dentro_do_anel(p, anel)
               for c, anel in _aneis())


def distancia_da_fronteira_km(p: Ponto) -> float:
    """Distância de `p` até o contorno mais próximo (projeção plana em volta de `p`)."""
    kx = 111.32 * math.cos(math.radians(p[0]))
    ky = 110.57
    melhor = float("inf")
    for _, anel in _aneis():
        for (la1, lo1), (la2, lo2) in zip(anel, anel[1:] + anel[:1]):
            ax, ay = (lo1 - p[1]) * kx, (la1 - p[0]) * ky
            bx, by = (lo2 - p[1]) * kx, (la2 - p[0]) * ky
            dx, dy = bx - ax, by - ay
            seg = dx * dx + dy * dy
            t = 0.0 if seg == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg))
            d = math.hypot(ax + t * dx, ay + t * dy)
            if d < melhor:
                melhor = d
    return melhor


def no_brasil(p: Ponto, margem_km: float = MARGEM_KM) -> bool:
    """Se `p` fica no Brasil, aceitando até `margem_km` fora do contorno."""
    if _dentro_do_contorno(p):
        return True
    return margem_km > 0 and distancia_da_fronteira_km(p) <= margem_km


def pontos_fora(pontos: list[Ponto], passo_km: float = PASSO_KM) -> list[Ponto]:
    """Os pontos da rota, a cada `passo_km`, que ficam fora do Brasil (com a margem)."""
    from . import geo  # geo importa este módulo
    amostra = [pontos[0]] + [p for _, p in geo.amostrar(pontos, passo_km)] + [pontos[-1]] if pontos else []
    return [p for p in amostra if not no_brasil(p)]


def ponto_de_passagem(fora: list[Ponto], maximo_candidatos: int = 300) -> Ponto | None:
    """Sede de município no Brasil perto do trecho que saiu do país, com folga da fronteira.

    Pega o ponto do meio do trecho de fora e procura, da sede mais perto para a mais
    longe, a primeira que fica a FOLGA_PASSAGEM_KM da fronteira. None se não achar.
    """
    if not fora:
        return None
    meio = fora[len(fora) // 2]
    from . import geo
    sedes = sorted(((m["lat"], m["lon"]) for m in cidades._municipios()),
                   key=lambda s: geo.distancia_km(meio, s))
    for s in sedes[:maximo_candidatos]:
        if _dentro_do_contorno(s) and distancia_da_fronteira_km(s) >= FOLGA_PASSAGEM_KM:
            return s
    return None
