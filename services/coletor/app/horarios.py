"""O horário de hoje de um lugar, no fuso do lugar (HU11).

Responsabilidades:
- Saber o dia da semana no fuso da UF do lugar (o Brasil não tem horário de verão desde 2019).
- Achar as faixas desse dia nos horários do Google, do gosom ou do OpenStreetMap.
- Devolver as faixas sempre como "HH:MM–HH:MM", para o app não depender da fonte.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta

# Horas em relação a UTC; as UFs que faltam ficam em -3 (Brasília).
_FUSO_POR_UF = {"AM": -4, "RR": -4, "RO": -4, "MT": -4, "MS": -4, "AC": -5}
_FUSO_PADRAO = -3

# Índice de datetime.weekday(): 0 é segunda. O gosom pode mandar os dias em inglês.
_DIAS = ("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo")
_DIAS_EM_INGLES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_FECHADO = {"fechado", "closed"}
DIA_INTEIRO = "00:00–24:00"

_FAIXA = re.compile(r"(\d{1,2})[:h](\d{2})\s*[–—-]\s*(\d{1,2})[:h](\d{2})")
_VINTE_E_QUATRO = re.compile(r"24\s*(horas|hours)")

# opening_hours do OSM: só a forma simples, "Mo-Fr 08:00-18:00; Sa 08:00-12:00,14:00-17:00; Su off".
_DIAS_OSM = ("mo", "tu", "we", "th", "fr", "sa", "su")
_REGRA_OSM = re.compile(r"(?P<dias>[A-Za-z]{2}(-[A-Za-z]{2})?(,[A-Za-z]{2}(-[A-Za-z]{2})?)*)\s+"
                        r"(?P<horas>off|closed|\d{2}:\d{2}-\d{2}:\d{2}(,\d{2}:\d{2}-\d{2}:\d{2})*)")


def _simples(texto: str) -> str:
    """Sem acento e minúsculo; os espaços estreitos do Google viram espaço comum."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().strip()


def _dia(nome: str) -> str:
    """"Terça-feira" -> "terca"; "Tuesday" -> "terca"."""
    dia = _simples(nome).split("-")[0]
    return _DIAS[_DIAS_EM_INGLES.index(dia)] if dia in _DIAS_EM_INGLES else dia


def _faixa(texto: str) -> str | None:
    """"8:00 – 12:00" -> "08:00–12:00"; "Atendimento 24 horas" -> o dia inteiro; fechado -> None."""
    simples = _simples(texto)
    if simples in _FECHADO:
        return None
    if _VINTE_E_QUATRO.search(simples):
        return DIA_INTEIRO
    achado = _FAIXA.search(texto)
    if not achado:
        return texto.strip()
    h1, m1, h2, m2 = achado.groups()
    return f"{int(h1):02d}:{m1}–{int(h2):02d}:{m2}"


def _dias_da_regra(dias: str) -> set[int] | None:
    """"Mo-Fr,Su" -> {0, 1, 2, 3, 4, 6}; um intervalo como "Fr-Mo" dá a volta na semana."""
    saida = set()
    for parte in dias.lower().split(","):
        ini, _, fim = parte.partition("-")
        if ini not in _DIAS_OSM or (fim and fim not in _DIAS_OSM):
            return None
        a, b = _DIAS_OSM.index(ini), _DIAS_OSM.index(fim or ini)
        saida.update((a + i) % 7 for i in range((b - a) % 7 + 1))
    return saida


def _do_osm(horarios: str, dia: int) -> list[str] | None:
    """As faixas do dia num opening_hours do OSM; None quando a regra é mais do que o leitor entende."""
    if horarios.strip() == "24/7":
        return [DIA_INTEIRO]
    faixas = None
    # Regra posterior vale sobre a anterior para o mesmo dia, como no OSM.
    for regra in filter(None, (r.strip() for r in horarios.split(";"))):
        achado = _REGRA_OSM.fullmatch(regra)
        dias = achado and _dias_da_regra(achado["dias"])
        if not dias:
            return None
        if dia in dias:
            horas = achado["horas"]
            faixas = [] if horas in ("off", "closed") else [f for f in map(_faixa, horas.split(",")) if f]
    # Dia que nenhuma regra cita fica desconhecido: melhor não mostrar do que dizer "fechado" errado.
    return faixas


def de_hoje(horarios: dict | str | None, uf: str | None, agora: datetime) -> list[str] | None:
    """As faixas de hoje no fuso do lugar.

    Args:
        horarios: Os horários do card, como a fonte devolveu.
        uf: A UF do lugar, que decide o fuso.
        agora: O instante atual, com fuso.

    Returns:
        As faixas de hoje ([] quando fecha hoje); None quando o horário de hoje não é conhecido.
    """
    local = agora + timedelta(hours=_FUSO_POR_UF.get((uf or "").upper(), _FUSO_PADRAO))
    hoje = _DIAS[local.weekday()]
    if isinstance(horarios, dict):
        for nome, faixas in horarios.items():
            if _dia(nome) == hoje:
                # uma fonte pode mandar o dia como texto só ("8:00–18:00"), não como lista
                lista = [faixas] if isinstance(faixas, str) else faixas or []
                return [f for f in map(_faixa, lista) if f]
    if isinstance(horarios, str):
        return _do_osm(horarios, local.weekday())
    return None
