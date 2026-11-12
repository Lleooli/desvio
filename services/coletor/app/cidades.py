"""Autocompletar de cidade com UF, a partir da lista local de municípios do IBGE.

A lista (app/referencia/municipios.csv) tem os municípios do Brasil (5.571
linhas, com o Distrito Federal) e a coordenada da sede. Ela vem de
github.com/kelvins/municipios-brasileiros (licença MIT em
app/referencia/LICENSE-municipios.txt, dados do IBGE). Buscar aqui, e não no Nominatim, responde em milissegundos e não
gasta a cota de 1 requisição por segundo enquanto a pessoa digita.
"""
from __future__ import annotations

import csv
import functools
import re
import unicodedata
from pathlib import Path

ARQUIVO = Path(__file__).parent / "referencia" / "municipios.csv"
UFS = {"AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE",
       "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"}
MINIMO_LETRAS = 3
LIMITE = 8


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


@functools.cache
def _municipios() -> list[dict]:
    with open(ARQUIVO, encoding="utf-8", newline="") as f:
        return [{"nome": l["nome"], "uf": l["uf"], "rotulo": f'{l["nome"]}, {l["uf"]}',
                 "lat": float(l["lat"]), "lon": float(l["lon"]), "codigo_ibge": l["codigo_ibge"],
                 "_capital": l["capital"] == "1", "_norm": normalizar(l["nome"])}
                for l in csv.DictReader(f)]


def _separar_uf(q: str) -> tuple[str, str | None]:
    """'lages, sc' ou 'lages sc' -> ('lages', 'SC'). Só tira a UF se sobrar nome antes."""
    texto, virgula, resto = q.rpartition(",")
    if virgula and normalizar(resto).upper() in UFS:
        return normalizar(texto), normalizar(resto).upper()
    partes = normalizar(q).split(" ")
    if len(partes) >= 2 and partes[-1].upper() in UFS:
        return " ".join(partes[:-1]), partes[-1].upper()
    return normalizar(q), None


def _publico(m: dict) -> dict:
    return {k: v for k, v in m.items() if not k.startswith("_")}


@functools.lru_cache(maxsize=2048)
def _buscar(q: str, limite: int) -> tuple[dict, ...]:
    nome, uf = _separar_uf(q)
    if len(nome.replace(" ", "")) < MINIMO_LETRAS:
        return ()
    achados = []
    for m in _municipios():
        if uf and m["uf"] != uf:
            continue
        n = m["_norm"]
        if n.startswith(nome):
            nivel = 0  # "lag" -> Lages
        elif (" " + nome) in (" " + n):
            nivel = 1  # "conquista" -> Vitória da Conquista
        else:
            continue
        achados.append((nivel, not m["_capital"], len(n), n, m["uf"], m))
    achados.sort(key=lambda a: a[:5])
    return tuple(_publico(a[-1]) for a in achados[:limite])


def buscar(q: str, limite: int = LIMITE) -> list[dict]:
    """Até `limite` municípios cujo nome começa com `q` (ou tem uma palavra que começa)."""
    return [dict(c) for c in _buscar(q or "", limite)]


def exata(lugar: str) -> dict | None:
    """'Cidade, UF' exatamente como na lista (acento e caixa opcionais); senão None."""
    nome, uf = _separar_uf(lugar)
    if not uf or "," not in lugar:
        return None
    for m in _municipios():
        if m["uf"] == uf and m["_norm"] == nome:
            return _publico(m)
    return None
