"""Guarda cada swipe (tabelas `lugar` e `decisao` do Postgres) e resume o gosto do usuário.

O resumo (perfil) é o que vai no prompt da IA para ela recomendar com base nas
decisões anteriores, e também serve para pré-ordenar os próximos cards.
"""
from __future__ import annotations

import re
from collections import defaultdict

from psycopg.types.json import Jsonb

from . import banco


# Campos do card que entram no perfil; ficam na decisão de cada pessoa (#61)
CAMPOS_PERFIL = ("categoria", "tipo", "faixa_preco", "nota")

# `lugar` é público (RLS de leitura para todos) e o card vem do cliente: só entram os
# campos que o coletor produz, com tamanho limitado, e só ids no formato do coletor.
CAMPOS_LUGAR = ("id", "fonte", "nome", "categoria", "tipo", "cidade", "uf", "lat", "lon", "foto", "fotos",
                "nota", "avaliacoes", "faixa_preco", "descricao", "sobre", "endereco", "site", "telefone",
                "instagram", "instagram_origem", "wikipedia", "horarios", "link_maps")
ID_VALIDO = re.compile(r"(osm|gmaps):[\w.:/-]{1,120}")
MAX_TEXTO = 1000
MAX_LISTA = 10


def _valor_limpo(v):
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return v[:MAX_TEXTO]
    if isinstance(v, list):
        return [x[:MAX_TEXTO] for x in v[:MAX_LISTA] if isinstance(x, str)]
    return None  # objeto aninhado não faz parte de um card


def card_limpo(card: dict) -> dict:
    """Só os campos conhecidos do card, com textos e listas cortados. ValueError se o id não vale."""
    if not isinstance(card.get("id"), str) or not ID_VALIDO.fullmatch(card["id"]):
        raise ValueError("id de card inválido")
    return {k: _valor_limpo(card[k]) for k in CAMPOS_LUGAR if k in card}


def registrar(usuario: str, card: dict, gostou: bool, email: str | None = None) -> None:
    """Guarda o card em `lugar` (compartilhado entre pessoas) e a decisão em `decisao`
    (uma por pessoa e lugar; deslizar de novo troca a decisão).

    Tudo numa conexão e numa transação: garante a linha em `usuario`, o lugar e a
    decisão; se uma parte falha, nada fica gravado.

    O card vem do cliente, então nunca reescreve um `lugar` que já existe: só o
    primeiro swipe grava. O que entra no perfil fica na própria decisão, e assim o
    card de uma pessoa não muda o perfil de outra. Só entram campos conhecidos, com
    tamanho limitado (`card_limpo`).
    """
    card = card_limpo(card)
    with banco.conectar() as con:
        banco.garantir_usuario(usuario, email, con)
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
