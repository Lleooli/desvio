"""Guarda cada decisão (tabelas `lugar` e `decisao` do Postgres) e resume o gosto do usuário.

O resumo (perfil) é o que vai no prompt da IA para ela recomendar com base nas
decisões anteriores, e também serve para pré-ordenar os próximos cards.

Favorito é um Bora: entra no roteiro e conta como aceite na taxa do perfil.
O PRD não define multiplicador; a taxa continua aceitos/vistos, entre 0 e 1.
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict

from psycopg.types.json import Jsonb

from . import banco, pernoite


# Campos do card que entram no perfil; ficam na decisão de cada pessoa (#61)
CAMPOS_PERFIL = ("categoria", "tipo", "faixa_preco", "nota")
# Passo não é aceite. Bora e favorito contam 1: favorito pesa como aceite forte,
# sem estourar a taxa acima de 1 (HU16 fala em taxa de aceite).
ACEITE = {"bora": 1, "favorito": 1, "passo": 0}

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


class NaoEncontrado(LookupError):
    """Viagem ou parada que não é desta pessoa (a API responde 404)."""


def card_limpo(card: dict) -> dict:
    """Só os campos conhecidos do card, com textos e listas cortados. ValueError se o id não vale."""
    if not isinstance(card.get("id"), str) or not ID_VALIDO.fullmatch(card["id"]):
        raise ValueError("id de card inválido")
    return {k: _valor_limpo(card[k]) for k in CAMPOS_LUGAR if k in card}


def _tipo_da_decisao(tipo: str | bool) -> str:
    """`bool` é o contrato antigo (`gostou`): True vira bora, False vira passo."""
    if isinstance(tipo, bool):
        return "bora" if tipo else "passo"
    if tipo not in ACEITE:
        raise ValueError("tipo de decisão inválido")
    return tipo


def _viagem_e_parada(con, usuario: str, viagem: str | None, parada: int | None) -> tuple[str | None, int | None]:
    if parada is not None and viagem is None:
        raise ValueError("A parada precisa vir com a viagem")
    if viagem is None:
        return None, None
    try:
        viagem = str(uuid.UUID(viagem))
    except ValueError:
        raise NaoEncontrado("Viagem não encontrada") from None
    if not con.execute("select 1 from viagem where id = %s and usuario = %s", (viagem, usuario)).fetchone():
        raise NaoEncontrado("Viagem não encontrada")
    if parada is not None and not con.execute(
            "select 1 from parada where viagem = %s and ordem = %s", (viagem, parada)).fetchone():
        raise NaoEncontrado("Parada não encontrada")
    return viagem, parada


def registrar(usuario: str, card: dict, tipo: str | bool, email: str | None = None,
              *, viagem: str | None = None, parada: int | None = None) -> None:
    """Guarda o card em `lugar` (compartilhado entre pessoas) e a decisão em `decisao`
    (uma por pessoa e lugar; decidir de novo troca a decisão).

    `tipo` é bora, passo ou favorito. O bool antigo (`gostou`) ainda vale: True é bora.
    `viagem` e `parada` (a ordem da parada) ficam na decisão quando o app manda.

    Tudo numa conexão e numa transação: garante a linha em `usuario`, o lugar e a
    decisão; se uma parte falha, nada fica gravado.

    O card vem do cliente, então nunca reescreve um `lugar` que já existe: só a
    primeira decisão grava. O que entra no perfil fica na própria decisão, e assim o
    card de uma pessoa não muda o perfil de outra. Só entram campos conhecidos, com
    tamanho limitado (`card_limpo`).
    """
    card = card_limpo(card)
    tipo = _tipo_da_decisao(tipo)
    with banco.conectar() as con:
        banco.garantir_usuario(usuario, email, con)
        viagem, parada = _viagem_e_parada(con, usuario, viagem, parada)
        con.execute("insert into lugar (id, dados, fonte) values (%s, %s, %s) on conflict (id) do nothing",
                    (card["id"], Jsonb(card), card.get("fonte")))
        con.execute("insert into decisao (usuario, lugar, viagem, parada, tipo, card) "
                    "values (%s, %s, %s, %s, %s, %s) "
                    "on conflict (usuario, lugar) do update set tipo = excluded.tipo, card = excluded.card, "
                    "viagem = excluded.viagem, parada = excluded.parada, quando = now()",
                    (usuario, card["id"], viagem, parada, tipo,
                     Jsonb({k: card.get(k) for k in CAMPOS_PERFIL})))


def desfazer(usuario: str, lugar: str, email: str | None = None) -> bool:
    """Tira a decisão desta pessoa sobre o lugar. O lugar compartilhado fica.

    Sem a linha em `decisao`, o card volta para a fila da parada e o perfil deixa
    de contar a decisão. Devolve False se não havia o que desfazer.
    """
    if not isinstance(lugar, str) or not ID_VALIDO.fullmatch(lugar):
        raise ValueError("id de card inválido")
    with banco.conectar() as con:
        banco.garantir_usuario(usuario, email, con)
        cur = con.execute("delete from decisao where usuario = %s and lugar = %s", (usuario, lugar))
        return cur.rowcount > 0


def _nota(valor) -> float | None:
    return float(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) else None


def _respostas_limpas(respostas: list) -> list[dict]:
    """No máximo uma resposta por pergunta da triagem, com texto cortado."""
    from . import ia
    saida = []
    for item in respostas[:ia.MAX_PERGUNTAS]:
        if not isinstance(item, dict):
            continue
        resposta = item.get("resposta")
        if isinstance(resposta, str):
            resposta = resposta[:MAX_TEXTO]
        elif isinstance(resposta, list):
            resposta = [str(x)[:200] for x in resposta[:MAX_LISTA]]
        elif resposta is not None and not isinstance(resposta, (int, float, bool)):
            resposta = str(resposta)[:MAX_TEXTO]
        saida.append({"pergunta": str(item.get("pergunta") or "")[:MAX_TEXTO], "resposta": resposta})
    return saida


def _gosto(valor) -> dict:
    return valor if isinstance(valor, dict) else {}


def guardar_triagem(usuario: str, email: str | None, respostas: list, resumo: str | None, *,
                    pulou: bool) -> None:
    """Grava respostas e resumo em `usuario.perfil_gosto`, sem apagar outras chaves do JSON.

    Pular guarda o que já foi respondido e deixa o resumo vazio: o ranqueamento
    fica só na estatística. Concluir grava o resumo que a triagem devolveu.
    """
    respostas = _respostas_limpas(respostas)
    if not isinstance(resumo, str) or not resumo.strip():
        resumo = None
    else:
        resumo = resumo[:MAX_TEXTO]
    with banco.conectar() as con:
        banco.garantir_usuario(usuario, email, con)
        atual = con.execute("select perfil_gosto from usuario where id = %s", (usuario,)).fetchone()
        base = {**_gosto(atual["perfil_gosto"] if atual else None),
                "respostas": respostas, "resumo": resumo, "pulou": pulou}
        con.execute("update usuario set perfil_gosto = %s where id = %s", (Jsonb(base), usuario))


def ajustar(usuario: str, email: str | None, mudancas: dict) -> None:
    """Grava o que a pessoa mudou no perfil: `tema`, `intervalo_km` e `resumo` da triagem.

    Args:
        usuario: Id da pessoa.
        email: E-mail do token, para criar a linha em `usuario` se faltar.
        mudancas: Só as chaves enviadas; as que faltam ficam como estão.
    """
    with banco.conectar() as con:
        banco.garantir_usuario(usuario, email, con)
        for coluna in ("tema", "intervalo_km"):
            if coluna in mudancas:
                con.execute(f"update usuario set {coluna} = %s where id = %s", (mudancas[coluna], usuario))
        if "resumo" in mudancas:
            # a pessoa corrige o que a IA entendeu; as respostas da triagem ficam
            resumo = mudancas["resumo"].strip() or None
            con.execute("update usuario set perfil_gosto = coalesce(perfil_gosto, '{}'::jsonb) "
                        "|| jsonb_build_object('resumo', %s::text) where id = %s", (resumo, usuario))


def perfil(usuario: str) -> dict:
    with banco.conectar() as con:
        # o card que a própria pessoa viu; decisões de antes do #61 não têm e usam o lugar
        rs = con.execute("select d.tipo, coalesce(d.card, l.dados) as dados from decisao d "
                         "join lugar l on l.id = d.lugar where d.usuario = %s", (usuario,)).fetchall()
        u = con.execute("select perfil_gosto, tema, intervalo_km from usuario where id = %s",
                        (usuario,)).fetchone() or {}
    gosto = _gosto(u.get("perfil_gosto"))
    # (aceite, categoria, tipo, faixa_preco, nota); favorito conta como aceite, igual ao bora
    linhas = [(ACEITE.get(r["tipo"], 0), r["dados"].get("categoria"), r["dados"].get("tipo"),
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
    # a estatística das decisões e a triagem ficam juntas na resposta; a coluna só guarda a triagem
    return {"total_swipes": len(linhas), "aceitos": sum(l[0] for l in linhas),
            "nota_media_aceitos": round(sum(notas) / len(notas), 2) if notas else None, **taxa,
            "resumo": gosto.get("resumo"), "respostas": gosto.get("respostas") or [],
            "pulou": bool(gosto.get("pulou")), "tema": u.get("tema") or "sistema",
            "intervalo_km": u.get("intervalo_km")}


def ja_vistos(usuario: str) -> set[str]:
    with banco.conectar() as con:
        return {r["lugar"] for r in con.execute("select lugar from decisao where usuario = %s", (usuario,))}


def pontuar(cards: list[dict], p: dict, ordem_generica: bool = False) -> list[dict]:
    """Ordena os cards novos pelo gosto aprendido (sem IA, só estatística).

    Com `ordem_generica` (os cards vêm na ordem da IA para a cidade, #93), a posição
    ocupa o lugar da nota na conta: o primeiro da IA vale 0,5, como uma nota 5, e o
    gosto da pessoa mexe em cima disso.
    """
    pos = {id(c): i for i, c in enumerate(cards)}

    def score(c: dict) -> float:
        s = 0.5
        for campo in ("categoria", "tipo", "faixa_preco"):
            info = p.get(campo, {}).get(c.get(campo) or "")
            if info:
                s += info["taxa"] - 0.5
        if ordem_generica:
            return s + 0.5 * (1 - pos[id(c)] / len(cards))
        return s + (c.get("nota") or 0) / 10
    return sorted(cards, key=score, reverse=True)


def personalizar(resultado: dict, usuario: str | None, perfil_pronto: dict | None = None) -> dict:
    """Tira cards já avaliados e ordena os novos pelo gosto estatístico do usuário."""
    if not usuario:
        return resultado
    vistos = ja_vistos(usuario)
    p = perfil(usuario) if perfil_pronto is None else perfil_pronto
    for parada in resultado["paradas"]:
        parada["cards"] = pontuar([c for c in parada["cards"] if c["id"] not in vistos], p,
                                  bool(parada.get("ranqueada")))
    pernoite.hoteis_primeiro(resultado["paradas"])  # na estadia, os hotéis antes do gosto
    return resultado
