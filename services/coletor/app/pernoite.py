"""Pernoite planejado na coleta (issue #104).

Com a duração da rota, o veículo e a hora de saída, `pontos` acha onde cada dia de
estrada acaba, com as mesmas regras da agenda do roteiro (roteiro.HORAS_VOLANTE e o fim
do dia às 22h). Em cada um desses pontos a viagem precisa de uma cidade para dormir: a
parada que já está perto (folga de PV_FOLGA_PARADA_PCT do intervalo) vira estadia; sem
ela, `planejar` pergunta a cidade mais perto do ponto e insere uma parada nova.

A parada de estadia sai com `tipo: "estadia"` e `dia` (a noite do dia N), e sempre busca
hospedagem, mesmo sem a categoria marcada (`categorias_da_parada`); no swipe os hotéis vêm
primeiro (`hoteis_primeiro`).

Tudo aqui é puro, menos `planejar`, que recebe de quem chama a função que acha a cidade.
"""
from __future__ import annotations

import bisect
import logging
import os
import re
import unicodedata
from collections.abc import Awaitable, Callable

from . import roteiro

log = logging.getLogger("desvio.pernoite")

# Folga para aproveitar uma parada que já existe como estadia, em % do intervalo entre
# paradas (a mesma variável da #93).
FOLGA_PCT = float(os.getenv("PV_FOLGA_PARADA_PCT", "10"))
SAIDA_PADRAO = "07:00"
# Sem cidade no ponto exato, tenta antes dele (o dia fica mais curto, nunca mais longo),
# recuando estas frações do intervalo entre paradas
RECUOS = (0.0, 0.25, 0.5)


def _norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def folga_km(intervalo_km: float) -> float:
    return max(0.0, intervalo_km * FOLGA_PCT / 100)


def pontos(duracao_h: float, distancia_km: float, veiculo: str = "carro",
           saida: str | None = None) -> list[dict]:
    """Onde cada dia de estrada acaba: [{dia, horas_desde_saida, km}], sem o dia da chegada.

    O dia tem no máximo roteiro.HORAS_VOLANTE[veiculo] horas de estrada e acaba às 22h;
    o primeiro começa na `saida` (07:00 sem ela) e os seguintes na mesma hora, se ela
    fica entre 5h e 10h, ou às 8h. Saída depois das 22h não roda no primeiro dia.
    """
    if duracao_h <= 0 or distancia_km <= 0:
        return []
    limite = roteiro.HORAS_VOLANTE.get(veiculo, roteiro.HORAS_VOLANTE["carro"]) * 60
    inicio = roteiro.minutos(saida)
    inicio = roteiro.minutos(SAIDA_PADRAO) if inicio is None else inicio
    seguintes = inicio if 5 * 60 <= inicio <= 10 * 60 else roteiro.INICIO_PADRAO
    total = duracao_h * 60
    feito, dia, comeco = 0.0, 1, inicio
    noites: list[dict] = []
    while True:
        cabe = max(0, min(limite, roteiro.FIM_DO_DIA - comeco))
        if total - feito <= cabe:
            return noites
        if cabe:
            feito += cabe
            noites.append({"dia": dia, "horas_desde_saida": round(feito / 60, 2),
                           "km": feito / total * distancia_km})
        dia, comeco = dia + 1, seguintes


def ponto_no_km(pontos_rota: list[tuple[float, float]], acc: list[float], km: float) -> tuple[float, float]:
    """O ponto da polilinha no km dado (interpolado entre os vértices)."""
    km = min(max(km, 0.0), acc[-1])
    i = max(1, bisect.bisect_left(acc, km))
    if i >= len(acc):
        return pontos_rota[-1]
    a, b = pontos_rota[i - 1], pontos_rota[i]
    seg = acc[i] - acc[i - 1]
    f = (km - acc[i - 1]) / seg if seg else 0.0
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f


def marcar(paradas: list[dict], noites: list[dict], folga: float,
           com_hotel: list[dict] | tuple = ()) -> list[dict]:
    """Escolhe, dentro da folga, a cidade de cada noite entre as paradas e as cidades com hotel.

    `paradas` precisam de `km_na_rota`; o destino nunca vira estadia (é chegada).
    `com_hotel` são cidades (nome, uf, lat, lon, km, raio_km) que já têm hospedagem
    guardada (parada_cidade, #93): elas ganham das outras, e depois vale a mais perto.
    A parada escolhida vira estadia; a cidade com hotel que ainda não é parada entra nova.

    Returns:
        As noites que ficaram sem cidade perto, para `planejar` achar uma.
    """
    hoteis = {_norm(c["nome"]) for c in com_hotel}
    faltam = []
    for n in noites:
        nomes = {_norm(p["nome"]) for p in paradas}
        perto = [(_norm(p["nome"]) not in hoteis, abs(p["km_na_rota"] - n["km"]), 0, i)
                 for i, p in enumerate(paradas)
                 if p.get("tipo") == "parada" and abs(p["km_na_rota"] - n["km"]) <= folga]
        perto += [(False, abs(c["km"] - n["km"]), 1, i) for i, c in enumerate(com_hotel)
                  if _norm(c["nome"]) not in nomes and abs(c["km"] - n["km"]) <= folga]
        if not perto:
            faltam.append(n)
            continue
        _, _, nova, i = min(perto)
        if nova:
            c = com_hotel[i]
            inserir(paradas, {"nome": c["nome"], "uf": c.get("uf"), "lat": c["lat"], "lon": c["lon"],
                              "raio_km": c.get("raio_km"), "tipo": "estadia", "dia": n["dia"],
                              "km_na_rota": c["km"]})
        else:
            paradas[i]["tipo"], paradas[i]["dia"] = "estadia", n["dia"]
    return faltam


def inserir(paradas: list[dict], nova: dict) -> None:
    """Põe a parada na ordem do km, sempre antes do destino."""
    pos = next((i for i, p in enumerate(paradas)
                if p.get("tipo") == "destino" or p["km_na_rota"] > nova["km_na_rota"]), len(paradas))
    paradas.insert(pos, nova)


AcharCidade = Callable[[tuple[float, float]], Awaitable[dict | None]]


async def planejar(paradas: list[dict], noites: list[dict], *, intervalo_km: float,
                   ponto_do_km: Callable[[float], tuple[float, float]],
                   km_do_ponto: Callable[[tuple[float, float]], float],
                   achar_cidade: AcharCidade, excluir: set[str] = frozenset(),
                   com_hotel: list[dict] | tuple = ()) -> None:
    """Marca ou insere em `paradas` uma estadia por noite. Muda a lista no lugar.

    Args:
        paradas: As paradas da coleta, na ordem do km, cada uma com `km_na_rota`.
        noites: O que `pontos` devolveu.
        intervalo_km: Intervalo entre paradas (a folga e o recuo saem dele).
        ponto_do_km: (lat, lon) da rota num km.
        km_do_ponto: Km da rota mais perto de um (lat, lon).
        achar_cidade: A cidade (nome, uf, lat, lon, raio_km) perto de um ponto, ou None.
        excluir: Nomes (normalizados por `_norm`) que não podem ser estadia, como a origem.
        com_hotel: Cidades que já têm hospedagem guardada, com `km`; ganham dentro da folga.
    """
    com_hotel = [c for c in com_hotel if _norm(c["nome"]) not in excluir]
    for n in marcar(paradas, noites, folga_km(intervalo_km), com_hotel):
        for recuo in RECUOS:
            km = n["km"] - recuo * intervalo_km
            if km <= 0:
                break
            cidade = await achar_cidade(ponto_do_km(km))
            if not cidade or _norm(cidade["nome"]) in excluir:
                continue
            existente = next((p for p in paradas if _norm(p["nome"]) == _norm(cidade["nome"])), None)
            if existente is None:
                inserir(paradas, {**cidade, "tipo": "estadia", "dia": n["dia"],
                                  "km_na_rota": km_do_ponto((cidade["lat"], cidade["lon"]))})
            elif existente.get("tipo") == "parada":
                existente["tipo"], existente["dia"] = "estadia", n["dia"]
            elif existente.get("tipo") == "destino":
                continue  # a cidade mais perto é o destino: tenta antes dele
            break
        else:
            log.info("sem cidade para o pernoite do dia %s (km %.0f)", n["dia"], n["km"])


def categorias_da_parada(parada: dict, categorias: list[str]) -> list[str]:
    """As categorias que a coleta busca na parada: na estadia, hospedagem sempre, e primeiro."""
    if parada.get("tipo") != "estadia":
        return categorias
    return ["hospedagem", *(c for c in categorias if c != "hospedagem")]


def hoteis_primeiro(paradas: list[dict]) -> list[dict]:
    """Na estadia, os cards de hospedagem vão para o topo, sem mudar a ordem entre eles."""
    for p in paradas:
        if p.get("tipo") == "estadia" and p.get("cards"):
            p["cards"] = sorted(p["cards"], key=lambda c: c.get("categoria") != "hospedagem")
    return paradas
