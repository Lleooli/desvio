"""Monta a ordem de visita a partir dos cards que a pessoa aceitou no swipe.

Viagem por terra (carro, moto ou bicicleta): ordena pelo km na rota, o que
vem primeiro na estrada vem primeiro.

A IA entra depois, para ajustar o que a geometria não sabe: horário de
funcionamento, pôr do sol, almoço no meio do dia etc. Os dias, a hora de
chegada e o pernoite saem de `agendar`, sem IA: a IA recebe a agenda pronta e a
resposta dela é conferida contra ela (issue #95).
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from . import horarios

# Horas ao volante por dia. A duração da rota já vem do perfil do veículo (a bicicleta no
# OSRM de bike), então o limite é de horas de estrada, não de km.
HORAS_VOLANTE = {"carro": 9, "moto": 8, "bicicleta": 6}
FIM_DO_DIA = 22 * 60  # ninguém chega a um lugar depois das 22h: dorme antes
INICIO_PADRAO = 8 * 60  # saída dos dias seguintes quando a do primeiro é muito cedo ou tarde
# Minutos parados em cada lugar, por categoria
PERMANENCIA = {"restaurante": 60, "turismo": 60, "natureza": 90, "posto": 15, "hospedagem": 0}
PERMANENCIA_PADRAO = 45


def ordenar_na_rota(cards: list[dict]) -> list[dict]:
    return sorted(cards, key=lambda c: c.get("km_na_rota") or 0)


def minutos(hhmm: object) -> int | None:
    """"07:30" -> 450; None se não está no formato HH:MM."""
    hora = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", hhmm) if isinstance(hhmm, str) else None
    return int(hora[1]) * 60 + int(hora[2]) if hora else None


def hhmm(minuto: int) -> str:
    return f"{minuto // 60:02d}:{minuto % 60:02d}"


def _dia_da_semana(data: object, dia: int) -> int | None:
    """0 é segunda; None sem a data da saída."""
    if isinstance(data, str):
        try:
            data = date.fromisoformat(data)
        except ValueError:
            return None
    if not isinstance(data, date):
        return None
    return (data + timedelta(days=dia - 1)).weekday()


def agendar(itens: list[dict], saida: str | None = None, veiculo: str = "carro",
            data: str | date | None = None) -> list[dict]:
    """Os itens na ordem dada, cada um com `dia`, `pernoite` e, com a saída, `chegada` e `aberto_na_chegada`.

    O dia tem no máximo HORAS_VOLANTE[veiculo] horas de estrada e acaba às 22h. Quando o
    próximo trecho não cabe no dia, a pessoa dorme na cidade do último lugar
    (`pernoite` True nele); trecho maior que um dia inteiro vira dia só de estrada, com
    pernoite no caminho. `horas_desde_saida` de cada item dá o tempo de estrada entre eles.

    Sem `saida` (HH:MM), os dias contam a partir das 8h, mas sem `chegada`: hora inventada
    não vai para a tela nem para a IA. `aberto_na_chegada` é None quando o horário do lugar
    não é conhecido; sem `data`, só é False se o lugar fecha nessa hora todos os dias.
    """
    limite = HORAS_VOLANTE.get(veiculo, HORAS_VOLANTE["carro"]) * 60
    inicio = minutos(saida)
    com_hora = inicio is not None
    inicio = INICIO_PADRAO if inicio is None else inicio
    inicio_seguintes = inicio if 5 * 60 <= inicio <= 10 * 60 else INICIO_PADRAO
    dia, relogio, volante, h_anterior = 1, inicio, 0, 0.0
    parou_hoje = False
    saida_itens: list[dict] = []
    for c in itens:
        h = c.get("horas_desde_saida")
        h = float(h) if isinstance(h, (int, float)) else h_anterior
        trecho = round(abs(h - h_anterior) * 60)
        h_anterior = h
        while volante + trecho > limite or relogio + trecho > FIM_DO_DIA:
            if volante == 0 and not parou_hoje:
                # dia que começa já sem caber o trecho: o dia inteiro é estrada
                trecho -= max(0, min(limite, FIM_DO_DIA - relogio))
            elif saida_itens and saida_itens[-1]["dia"] == dia:
                saida_itens[-1]["pernoite"] = True  # dorme na cidade do último lugar do dia
            dia, relogio, volante, parou_hoje = dia + 1, inicio_seguintes, 0, False
        relogio += trecho
        volante += trecho
        parou_hoje = True
        item = {**c, "dia": dia, "pernoite": False}
        item.pop("chegada", None)
        item.pop("aberto_na_chegada", None)
        if com_hora:
            item["chegada"] = hhmm(relogio)
            item["aberto_na_chegada"] = horarios.aberto(c.get("horarios"), relogio, _dia_da_semana(data, dia))
        saida_itens.append(item)
        relogio += PERMANENCIA.get(c.get("categoria") or "", PERMANENCIA_PADRAO)
    return saida_itens
