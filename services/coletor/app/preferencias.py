"""Guarda cada swipe e resume o gosto do usuário.

O resumo (perfil) é o que vai no prompt da IA para ela recomendar com base nas
decisões anteriores, e também serve para pré-ordenar os próximos cards.
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections import defaultdict
from contextlib import closing

DB = os.getenv("PV_DB", "planejador.db")


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS swipes (
        usuario TEXT, card_id TEXT, gostou INTEGER, categoria TEXT, tipo TEXT,
        faixa_preco TEXT, nota REAL, cidade TEXT, card TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (usuario, card_id))""")
    return con


def registrar(usuario: str, card: dict, gostou: bool) -> None:
    with closing(_con()) as con, con:
        con.execute("INSERT OR REPLACE INTO swipes (usuario, card_id, gostou, categoria, tipo, faixa_preco, nota, cidade, card)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (usuario, card["id"], int(gostou), card.get("categoria"), card.get("tipo"),
                     card.get("faixa_preco"), card.get("nota"), card.get("cidade"), json.dumps(card, ensure_ascii=False)))


def perfil(usuario: str) -> dict:
    with closing(_con()) as con:
        linhas = con.execute("SELECT gostou, categoria, tipo, faixa_preco, nota FROM swipes WHERE usuario=?",
                             (usuario,)).fetchall()
    taxa: dict[str, dict] = {}
    for campo, idx in (("categoria", 1), ("tipo", 2), ("faixa_preco", 3)):
        cont = defaultdict(lambda: [0, 0])
        for l in linhas:
            if l[idx]:
                cont[l[idx]][0] += l[0]
                cont[l[idx]][1] += 1
        taxa[campo] = {k: {"aceitos": a, "vistos": v, "taxa": round(a / v, 2)}
                       for k, (a, v) in sorted(cont.items(), key=lambda kv: -kv[1][1]) if v >= 2}
    notas = [l[4] for l in linhas if l[0] and l[4]]
    return {"total_swipes": len(linhas), "aceitos": sum(l[0] for l in linhas),
            "nota_media_aceitos": round(sum(notas) / len(notas), 2) if notas else None, **taxa}


def ja_vistos(usuario: str) -> set[str]:
    with closing(_con()) as con:
        return {r[0] for r in con.execute("SELECT card_id FROM swipes WHERE usuario=?", (usuario,))}


def pontuar(cards: list[dict], p: dict) -> list[dict]:
    """Ordena os cards novos pelo gosto aprendido (sem IA, só estatística)."""
    def score(c: dict) -> float:
        s = 0.5
        for campo in ("categoria", "tipo", "faixa_preco"):
            info = p.get(campo, {}).get(c.get(campo) or "")
            if info:
                s += info["taxa"] - 0.5
        return s + (c.get("nota") or 0) / 10
    return sorted(cards, key=score, reverse=True)
