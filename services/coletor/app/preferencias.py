"""Guarda cada swipe (tabelas `lugar` e `decisao` do Postgres) e resume o gosto do usuário.

O resumo (perfil) é o que vai no prompt da IA para ela recomendar com base nas
decisões anteriores, e também serve para pré-ordenar os próximos cards.
"""
from __future__ import annotations

from collections import defaultdict

from psycopg.types.json import Jsonb

from . import banco


# Campos do card que entram no perfil; ficam na decisão de cada pessoa (#61)
CAMPOS_PERFIL = ("categoria", "tipo", "faixa_preco", "nota")


def registrar(usuario: str, card: dict, gostou: bool) -> None:
    """Guarda o card em `lugar` (compartilhado entre pessoas) e a decisão em `decisao`
    (uma por pessoa e lugar; deslizar de novo troca a decisão).

    O card vem do cliente, então nunca reescreve um `lugar` que já existe: só o
    primeiro swipe grava. O que entra no perfil fica na própria decisão, e assim o
    card de uma pessoa não muda o perfil de outra.
    """
    with banco.conectar() as con:
        con.execute("insert into lugar (id, dados, fonte) values (%s, %s, %s) on conflict (id) do nothing",
                    (card["id"], Jsonb(card), card.get("fonte")))
        con.execute("insert into decisao (usuario, lugar, tipo, card) values (%s, %s, %s, %s) "
                    "on conflict (usuario, lugar) do update set tipo = excluded.tipo, card = excluded.card, "
                    "quando = now()",
                    (usuario, card["id"], "bora" if gostou else "passo",
                     Jsonb({k: card.get(k) for k in CAMPOS_PERFIL})))


def _nota(valor) -> float | None:
    return float(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) else None


def perfil(usuario: str) -> dict:
    with banco.conectar() as con:
        # o card que a própria pessoa viu; decisões de antes do #61 não têm e usam o lugar
        rs = con.execute("select d.tipo, coalesce(d.card, l.dados) as dados from decisao d "
                         "join lugar l on l.id = d.lugar where d.usuario = %s", (usuario,)).fetchall()
    # (gostou, categoria, tipo, faixa_preco, nota); favorito também conta como gostou
    linhas = [(int(r["tipo"] != "passo"), r["dados"].get("categoria"), r["dados"].get("tipo"),
               r["dados"].get("faixa_preco"), _nota(r["dados"].get("nota"))) for r in rs]
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
    with banco.conectar() as con:
        return {r["lugar"] for r in con.execute("select lugar from decisao where usuario = %s", (usuario,))}


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


def personalizar(resultado: dict, usuario: str | None) -> dict:
    """Tira cards já avaliados e ordena os novos pelo gosto do usuário."""
    if not usuario:
        return resultado
    vistos, p = ja_vistos(usuario), perfil(usuario)
    for parada in resultado["paradas"]:
        parada["cards"] = pontuar([c for c in parada["cards"] if c["id"] not in vistos], p)
    return resultado
