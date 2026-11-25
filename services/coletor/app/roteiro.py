"""Monta a ordem de visita a partir dos cards que a pessoa aceitou no swipe.

Viagem por terra (carro, moto ou bicicleta): ordena pelo km na rota, o que
vem primeiro na estrada vem primeiro.

A IA entra depois, para ajustar o que a geometria não sabe: horário de
funcionamento, pôr do sol, almoço no meio do dia etc. Os dias, a hora de
chegada e o pernoite saem de `agendar`, sem IA: a IA recebe a agenda pronta e a
resposta dela é conferida contra ela (issue #95).

Com as estadias que a coleta planejou (issue #104), os dias acabam nelas: a pessoa
dorme na cidade da estadia, no hotel que ela aceitou, e `noites` diz qual noite ainda
não tem hotel.
"""
from __future__ import annotations

import re
import unicodedata
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


def _chave(nome: object) -> str:
    texto = unicodedata.normalize("NFKD", nome if isinstance(nome, str) else "")
    return re.sub(r"[^a-z0-9]", "", texto.encode("ascii", "ignore").decode().lower())


def _horas(c: dict) -> float | None:
    h = c.get("horas_desde_saida")
    return float(h) if isinstance(h, (int, float)) else None


def _estadias_validas(estadias: list[dict] | None) -> list[dict]:
    """As estadias com dia, nome e horas, na ordem da estrada."""
    return sorted((e for e in estadias or () if isinstance(e.get("dia"), int) and e.get("nome")
                   and _horas(e) is not None), key=lambda e: (_horas(e), e["dia"]))


def _estadia_do_lugar(c: dict, estadias: list[dict]) -> dict | None:
    cidade = _chave(c.get("cidade"))
    return next((e for e in estadias if cidade and _chave(e["nome"]) == cidade), None) if cidade else None


def _dia_planejado(c: dict, estadias: list[dict]) -> int:
    """O dia do lugar pelas estadias: o da noite, na cidade dela; senão, o dia seguinte à última noite antes dele."""
    e = _estadia_do_lugar(c, estadias)
    if e:
        return e["dia"]
    h = _horas(c) or 0.0
    antes = [e["dia"] for e in estadias if _horas(e) < h]
    return max(antes) + 1 if antes else 1


def _hotel_da_noite(c: dict, estadias: list[dict]) -> bool:
    return c.get("categoria") == "hospedagem" and _estadia_do_lugar(c, estadias) is not None


def ordenar_na_rota(cards: list[dict], estadias: list[dict] | None = None) -> list[dict]:
    """Pelo km; com estadias, por dia e com o hotel da noite no fim do dia dele."""
    estadias = _estadias_validas(estadias)
    if not estadias:
        return sorted(cards, key=lambda c: c.get("km_na_rota") or 0)
    return sorted(cards, key=lambda c: (_dia_planejado(c, estadias), _hotel_da_noite(c, estadias),
                                        c.get("km_na_rota") or 0))


def minutos(hhmm: object) -> int | None:
    """"07:30" -> 450; None se não está no formato HH:MM."""
    hora = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", hhmm) if isinstance(hhmm, str) else None
    return int(hora[1]) * 60 + int(hora[2]) if hora else None


def hhmm(minuto: int) -> str:
    minuto %= 24 * 60
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
            data: str | date | None = None, estadias: list[dict] | None = None) -> list[dict]:
    """Os itens na ordem dada, cada um com `dia`, `pernoite` e, com a saída, `chegada` e `aberto_na_chegada`.

    O dia tem no máximo HORAS_VOLANTE[veiculo] horas de estrada e acaba às 22h. Quando o
    próximo trecho não cabe no dia, a pessoa dorme na cidade do último lugar
    (`pernoite` True nele); trecho maior que um dia inteiro vira dia só de estrada, com
    pernoite no caminho. `horas_desde_saida` de cada item dá o tempo de estrada entre eles.

    Sem `saida` (HH:MM), os dias contam a partir das 8h, mas sem `chegada`: hora inventada
    não vai para a tela nem para a IA. `aberto_na_chegada` é None quando o horário do lugar
    não é conhecido; sem `data`, só é False se o lugar fecha nessa hora todos os dias.

    Com `estadias` (as paradas de estadia da viagem: nome, dia e horas_desde_saida), os
    dias acabam nelas, como a coleta planejou com as mesmas horas ao volante: o lugar na
    cidade da estadia fica no dia da noite, e o hotel aceito nela tem `pernoite` True.
    """
    if _estadias_validas(estadias):
        return _agendar_nas_estadias(itens, saida, data, _estadias_validas(estadias))
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


def _inicios(saida: str | None) -> tuple[bool, int, int]:
    inicio = minutos(saida)
    com_hora = inicio is not None
    inicio = INICIO_PADRAO if inicio is None else inicio
    return com_hora, inicio, inicio if 5 * 60 <= inicio <= 10 * 60 else INICIO_PADRAO


def _agendar_nas_estadias(itens: list[dict], saida: str | None, data: str | date | None,
                          estadias: list[dict]) -> list[dict]:
    """`agendar` com os dias planejados na coleta: cada dia acaba na estadia dele."""
    com_hora, inicio, inicio_seguintes = _inicios(saida)
    horas_da_noite = {e["dia"]: _horas(e) for e in estadias}
    dia, relogio, h_anterior = 1, inicio, 0.0
    saida_itens: list[dict] = []
    for c in itens:
        h = _horas(c)
        h = h_anterior if h is None else h
        novo = max(_dia_planejado(c, estadias), dia)  # a ordem dada nunca volta um dia
        if novo != dia:
            dia, relogio = novo, inicio_seguintes
            h_anterior = horas_da_noite.get(dia - 1, h_anterior)  # o dia começa na cidade da noite
        relogio += round(abs(h - h_anterior) * 60)
        h_anterior = h
        item = {**c, "dia": dia, "pernoite": False}
        item.pop("chegada", None)
        item.pop("aberto_na_chegada", None)
        if com_hora:
            item["chegada"] = hhmm(relogio)
            item["aberto_na_chegada"] = horarios.aberto(c.get("horarios"), relogio % (24 * 60),
                                                        _dia_da_semana(data, dia))
        saida_itens.append(item)
        relogio += PERMANENCIA.get(c.get("categoria") or "", PERMANENCIA_PADRAO)
    for e in estadias:  # dorme no primeiro hotel aceito na cidade da noite
        hotel = next((i for i in saida_itens if i["dia"] == e["dia"] and _hotel_da_noite(i, [e])), None)
        if hotel:
            hotel["pernoite"] = True
    return saida_itens


def noites(itens: list[dict], estadias: list[dict] | None) -> list[dict]:
    """Uma linha por noite planejada: a cidade, a parada (`ordem`) e o hotel aceito nela.

    Sem hotel aceito na cidade da estadia, `hotel` é None e `aviso` diz o que falta; o
    app leva a pessoa ao swipe da parada.
    """
    saida = []
    for e in sorted(_estadias_validas(estadias), key=lambda e: e["dia"]):
        hoteis = [i for i in itens if _hotel_da_noite(i, [e])]
        hotel = next((i for i in hoteis if i.get("pernoite")), hoteis[0] if hoteis else None)
        saida.append({"dia": e["dia"], "cidade": e["nome"], "uf": e.get("uf"), "parada": e.get("ordem"),
                      "hotel": {"id": hotel["id"], "nome": hotel.get("nome")} if hotel else None,
                      "aviso": None if hotel else f'Falta escolher onde dormir em {e["nome"]}'})
    return saida
