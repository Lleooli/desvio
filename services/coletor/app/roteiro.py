"""Monta a ordem de visita a partir dos cards que a pessoa aceitou no swipe.

Viagem por terra (carro, moto ou bicicleta): ordena pelo km na rota, o que
vem primeiro na estrada vem primeiro.

A IA entra depois, para ajustar o que a geometria não sabe: horário de
funcionamento, pôr do sol, almoço no meio do dia etc.
"""
from __future__ import annotations


def ordenar_na_rota(cards: list[dict]) -> list[dict]:
    return sorted(cards, key=lambda c: c.get("km_na_rota") or 0)
