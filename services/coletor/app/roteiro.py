"""Monta a ordem de visita a partir dos cards que o usuário aceitou no swipe.

- Carro: ordena pelo km na rota (o que vem primeiro na estrada, primeiro).
- Cidade: resolve um "caixeiro viajante" pequeno (vizinho mais próximo + 2-opt)
  saindo do hotel/centro e divide a rota em blocos contíguos, um por dia.
  Blocos contíguos de um percurso curto ficam geograficamente agrupados,
  então cada dia cobre uma região da cidade.

A IA entra depois, para ajustar o que a geometria não sabe: horário de
funcionamento, pôr do sol, almoço no meio do dia etc.
"""
from __future__ import annotations

import math

from .geo import Ponto, distancia_km


def _pt(c: dict) -> Ponto:
    return (c["lat"], c["lon"])


def ordenar_carro(cards: list[dict]) -> list[dict]:
    return sorted(cards, key=lambda c: c.get("km_na_rota", 0))


def _custo(inicio: Ponto, rota: list[dict]) -> float:
    total, atual = 0.0, inicio
    for c in rota:
        total += distancia_km(atual, _pt(c))
        atual = _pt(c)
    return total


def _vizinho_mais_proximo(inicio: Ponto, cards: list[dict]) -> list[dict]:
    resto, rota, atual = cards[:], [], inicio
    while resto:
        prox = min(resto, key=lambda c: distancia_km(atual, _pt(c)))
        rota.append(prox)
        resto.remove(prox)
        atual = _pt(prox)
    return rota


def _dois_opt(inicio: Ponto, rota: list[dict]) -> list[dict]:
    melhor, custo = rota[:], _custo(inicio, rota)
    melhorou = True
    while melhorou:
        melhorou = False
        for i in range(len(melhor) - 1):
            for j in range(i + 1, len(melhor)):
                nova = melhor[:i] + melhor[i:j + 1][::-1] + melhor[j + 1:]
                c = _custo(inicio, nova)
                if c < custo - 1e-9:
                    melhor, custo, melhorou = nova, c, True
    return melhor


def roteiro_cidade(cards: list[dict], dias: int, inicio: Ponto | None = None) -> list[dict]:
    if not cards:
        return []
    if inicio is None:
        inicio = (sum(c["lat"] for c in cards) / len(cards), sum(c["lon"] for c in cards) / len(cards))
    percurso = _dois_opt(inicio, _vizinho_mais_proximo(inicio, cards))
    dias = max(1, min(dias, len(percurso)))
    tam = math.ceil(len(percurso) / dias)
    blocos = [percurso[i:i + tam] for i in range(0, len(percurso), tam)]
    return [{"dia": n + 1,
             "km_estimados": round(_custo(inicio, bloco), 1),
             "paradas": [{"ordem": k + 1, **c} for k, c in enumerate(bloco)]}
            for n, bloco in enumerate(blocos)]
