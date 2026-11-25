"""Viagens guardadas no banco (tabelas `viagem`, `parada`, `parada_lugar`, `lugar` e `roteiro`).

Ciclo de vida:
1. `POST /viagem` cria a viagem com status `buscando` junto com o job (mesma transação),
   e ela já aparece em `GET /viagens`.
2. O worker termina a coleta e chama `gravar_resultado`: paradas, lugares e a ligação
   entre eles, e a viagem passa a `pronta`. Se a coleta quebra, `marcar_falha` (`falhou`).
3. Depois do swipe, `lugares_aceitos` traz os lugares de Bora ou Favorito pelo km; a API
   ordena (pelo km ou pela IA) e `guardar_roteiro` guarda em `roteiro`.

`lugar` é compartilhado entre pessoas. O /swipe nunca reescreve um lugar (o card vem do
cliente, #61), mas a coleta é dado do próprio servidor: aqui o lugar é atualizado com o
card mais recente (`dados` e `coletado_em`). O que é só desta rota (km e horas desde a
saída) fica em `parada_lugar`, não no lugar.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

from . import banco, horarios, ia, preferencias, roteiro

# Campos do card que dependem da rota desta viagem; não entram no `lugar` compartilhado
_DA_ROTA = ("km_na_rota", "horas_desde_saida")
# Campos da parada que têm coluna própria ou viram cards
_PARADA_COLUNAS = ("nome", "uf", "km_na_rota", "horas_desde_saida", "cards")


def criar(con: psycopg.Connection, usuario: str, entrada: dict) -> str:
    """Linha da viagem com status `buscando`, na transação de quem chamou."""
    l = con.execute(
        "insert into viagem (usuario, veiculo, origem, destino, intervalo_km, categorias) "
        "values (%s, %s, %s, %s, %s, %s) returning id",
        (usuario, entrada["veiculo"], entrada["origem"], entrada["destino"], entrada["intervalo_km"],
         list(entrada.get("categorias") or []))).fetchone()
    return str(l["id"])


def ligar_job(con: psycopg.Connection, viagem: str, job: str) -> None:
    con.execute("update viagem set job = %s where id = %s", (job, viagem))


def gravar_resultado(viagem: str, resultado: dict) -> None:
    """Grava paradas, lugares e cards da coleta e marca a viagem como `pronta`.

    Numa transação só; não mexe em `resultado`. Rodar de novo (job que voltou para
    a fila) troca as paradas antigas pelas novas.
    """
    with banco.conectar() as con:
        con.execute("delete from parada where viagem = %s", (viagem,))  # cascata em parada_lugar
        for ordem, p in enumerate(resultado.get("paradas", [])):
            extra = {k: v for k, v in p.items() if k not in _PARADA_COLUNAS}
            con.execute("insert into parada (viagem, ordem, cidade, uf, km, horas_desde_saida, dados) "
                        "values (%s, %s, %s, %s, %s, %s, %s)",
                        (viagem, ordem, p.get("nome") or "", p.get("uf"), p.get("km_na_rota"),
                         p.get("horas_desde_saida"), Jsonb(extra)))
            vistos: set[str] = set()
            for pos, c in enumerate(p.get("cards", [])):
                if not isinstance(c.get("id"), str) or c["id"] in vistos:
                    continue
                vistos.add(c["id"])
                dados = {k: v for k, v in c.items() if k not in _DA_ROTA}
                con.execute("insert into lugar (id, dados, fonte) values (%s, %s, %s) "
                            "on conflict (id) do update set dados = excluded.dados, fonte = excluded.fonte, "
                            "coletado_em = now()",
                            (c["id"], Jsonb(dados), c.get("fonte")))
                con.execute("insert into parada_lugar (viagem, parada, lugar, posicao, km_na_rota, "
                            "horas_desde_saida) values (%s, %s, %s, %s, %s, %s)",
                            (viagem, ordem, c["id"], pos, c.get("km_na_rota"), c.get("horas_desde_saida")))
        rota = resultado.get("rota") or {}
        con.execute("update viagem set status = 'pronta', polilinha = %s, atualizado_em = now() where id = %s",
                    (json.dumps(rota["polilinha"]) if rota.get("polilinha") else None, viagem))


def marcar_falha(viagem: str) -> None:
    with banco.conectar() as con:
        con.execute("update viagem set status = 'falhou', atualizado_em = now() where id = %s", (viagem,))


def veiculo(viagem: str) -> str | None:
    """O veículo da viagem (carro, moto ou bicicleta); None se ela não existe.

    Quem chama já conferiu que a viagem é da pessoa.
    """
    with banco.conectar() as con:
        l = con.execute("select veiculo from viagem where id = %s", (viagem,)).fetchone()
    return l["veiculo"] if l else None


def _resumo(l: dict) -> dict:
    return {"id": str(l["id"]), "origem": l["origem"], "destino": l["destino"], "veiculo": l["veiculo"],
            "intervalo_km": l["intervalo_km"], "categorias": l["categorias"], "status": l["status"],
            "job_id": l["job"], "criado_em": l["criado_em"].isoformat(),
            "atualizado_em": l["atualizado_em"].isoformat(),
            "progresso": {"decididos": l["decididos"], "total": l["total"]}}


_SELECT = """
select v.*,
       (select count(distinct pl.lugar) from parada_lugar pl where pl.viagem = v.id) as total,
       (select count(distinct pl.lugar) from parada_lugar pl
          join decisao d on d.lugar = pl.lugar and d.usuario = v.usuario
         where pl.viagem = v.id) as decididos
  from viagem v
"""


def listar(usuario: str) -> list[dict]:
    """As viagens da pessoa, a mais recente primeiro, com o progresso das decisões."""
    with banco.conectar() as con:
        ls = con.execute(_SELECT + " where v.usuario = %s order by v.criado_em desc, v.id",
                         (usuario,)).fetchall()
    return [_resumo(l) for l in ls]


def obter(usuario: str, viagem: str) -> dict | None:
    """A viagem com paradas e cards ainda não avaliados, ordenados pelo gosto.

    Viagem de outra pessoa (ou id que não é uuid) volta None, como se não existisse.
    """
    try:
        viagem = str(uuid.UUID(viagem))
    except ValueError:
        return None
    with banco.conectar() as con:
        v = con.execute(_SELECT + " where v.id = %s and v.usuario = %s", (viagem, usuario)).fetchone()
        if not v:
            return None
        paradas = con.execute("select ordem, cidade, uf, km, horas_desde_saida, dados from parada "
                              "where viagem = %s order by ordem", (viagem,)).fetchall()
        cards = con.execute("select pl.parada, pl.km_na_rota, pl.horas_desde_saida, l.dados, d.tipo as decisao "
                            "from parada_lugar pl join lugar l on l.id = pl.lugar "
                            "left join decisao d on d.lugar = pl.lugar and d.usuario = %s "
                            "where pl.viagem = %s order by pl.parada, pl.posicao",
                            (usuario, viagem)).fetchall()
    por_parada: dict[int, list[dict]] = {}
    agora = datetime.now(timezone.utc)
    # O contador da tela Paradas ("3 de 12"): Bora ou Favorito sobre todos os cards da parada,
    # contado antes de `personalizar` tirar os já avaliados.
    progresso: dict[int, dict] = {}
    for c in cards:
        por_parada.setdefault(c["parada"], []).append(
            {**c["dados"], "km_na_rota": c["km_na_rota"], "horas_desde_saida": c["horas_desde_saida"],
             "horario_hoje": horarios.de_hoje(c["dados"].get("horarios"), c["dados"].get("uf"), agora)})
        contagem = progresso.setdefault(c["parada"], {"aceitos": 0, "total": 0})
        contagem["total"] += 1
        contagem["aceitos"] += c["decisao"] in ("bora", "favorito")
    resultado = {"paradas": [{**p["dados"], "ordem": p["ordem"], "nome": p["cidade"], "uf": p["uf"],
                              "km_na_rota": p["km"], "horas_desde_saida": p["horas_desde_saida"],
                              "cards": por_parada.get(p["ordem"], []),
                              "progresso": progresso.get(p["ordem"], {"aceitos": 0, "total": 0})}
                             for p in paradas]}
    preferencias.personalizar(resultado, usuario)  # tira os já avaliados e ordena pelo gosto
    ia.reaplicar_cache(resultado["paradas"], preferencias.perfil(usuario).get("resumo"))
    return {**_resumo(v), "polilinha": json.loads(v["polilinha"]) if v["polilinha"] else None,
            "paradas": resultado["paradas"]}


def lugares_aceitos(usuario: str, viagem: str) -> list[dict] | None:
    """Os lugares da viagem com Bora ou Favorito, cada um uma vez só, na ordem do km.

    Args:
        usuario: Dono da viagem.
        viagem: Id da viagem.

    Returns:
        Os cards com `km_na_rota` e `horas_desde_saida` desta rota; None se a viagem não
        existe ou é de outra pessoa.
    """
    try:
        viagem = str(uuid.UUID(viagem))
    except ValueError:
        return None
    with banco.conectar() as con:
        if not con.execute("select 1 from viagem where id = %s and usuario = %s", (viagem, usuario)).fetchone():
            return None
        aceitos = con.execute("select pl.km_na_rota, pl.horas_desde_saida, l.dados from parada_lugar pl "
                              "join lugar l on l.id = pl.lugar "
                              "join decisao d on d.lugar = pl.lugar and d.usuario = %s "
                              "where pl.viagem = %s and d.tipo in ('bora', 'favorito') "
                              "order by pl.parada, pl.posicao", (usuario, viagem)).fetchall()
    # O mesmo lugar pode estar em duas paradas vizinhas: fica a primeira, a de menor km
    unicos: dict[str, dict] = {}
    for a in aceitos:
        unicos.setdefault(a["dados"]["id"], {**a["dados"], "km_na_rota": a["km_na_rota"],
                                             "horas_desde_saida": a["horas_desde_saida"]})
    return roteiro.ordenar_na_rota(list(unicos.values()))


def guardar_roteiro(viagem: str, r: dict) -> bool:
    """Guarda em `roteiro` o que `POST /viagens/{id}/roteiro` devolveu (`itens`, `explicacoes`, `fonte`).

    Só a própria pessoa (`fonte` "pessoa") sobrescreve a ordem que ela escolheu: a IA
    que responde depois de uma edição não a desfaz.

    Returns:
        False se o roteiro guardado é da pessoa e `r` não é; True se guardou.
    """
    with banco.conectar() as con:
        return con.execute(
            "insert into roteiro (viagem, itens, explicacao, fonte) values (%s, %s, %s, %s) "
            "on conflict (viagem) do update set itens = excluded.itens, explicacao = excluded.explicacao, "
            "fonte = excluded.fonte, atualizado_em = now() "
            "where excluded.fonte = 'pessoa' or roteiro.fonte <> 'pessoa' returning viagem",
            (viagem, Jsonb(r["itens"]), Jsonb(r["explicacoes"]) if r["explicacoes"] else None, r["fonte"]),
        ).fetchone() is not None


def editar_roteiro(usuario: str, viagem: str, ids: list[str]) -> dict | None:
    """Guarda em `roteiro` a ordem que a pessoa escolheu; quem ficou de fora sai do roteiro.

    A decisão Bora (ou Favorito) de quem sai continua em `decisao`: só o roteiro muda.

    Args:
        usuario: Dono da viagem.
        viagem: Id da viagem.
        ids: Os ids dos lugares, na ordem de visita.

    Returns:
        O roteiro como o POST devolve (`itens`, `explicacoes`, `fonte` "pessoa"); None se a
        viagem não existe ou é de outra pessoa.

    Raises:
        ValueError: Id repetido ou de lugar que não tem Bora nesta viagem.
    """
    aceitos = lugares_aceitos(usuario, viagem)
    if aceitos is None:
        return None
    por_id = {a["id"]: a for a in aceitos}
    if len(set(ids)) != len(ids) or not set(ids) <= por_id.keys():
        raise ValueError("lugar fora do roteiro")
    r = {"itens": [por_id[i] for i in ids], "explicacoes": {}, "fonte": "pessoa"}
    # Ordem e removidos num comando só: uma leitura no meio nunca vê a ordem nova com os
    # removidos antigos (o lugar tirado voltaria).
    with banco.conectar() as con:
        con.execute(
            "insert into roteiro (viagem, itens, explicacao, fonte, removidos) values (%s, %s, null, 'pessoa', %s) "
            "on conflict (viagem) do update set itens = excluded.itens, explicacao = null, fonte = 'pessoa', "
            "removidos = excluded.removidos, atualizado_em = now()",
            (viagem, Jsonb(r["itens"]), sorted(por_id.keys() - set(ids))),
        )
    return r


def lugares_do_roteiro(usuario: str, viagem: str) -> dict | None:
    """O roteiro da viagem sem IA: os lugares aceitos, sem os que a pessoa tirou.

    Se a pessoa já editou o roteiro, a ordem é a dela (`fonte` "pessoa") e um lugar
    aceito depois entra antes do primeiro de km maior; senão, a ordem é a do km
    (`fonte` "geometria").

    Returns:
        `itens`, `explicacoes` e `fonte`, como o POST devolve; None se a viagem não
        existe ou é de outra pessoa.
    """
    aceitos = lugares_aceitos(usuario, viagem)
    if aceitos is None:
        return None
    with banco.conectar() as con:
        l = con.execute("select itens, fonte, removidos from roteiro where viagem = %s", (viagem,)).fetchone()
    removidos = set(l["removidos"]) if l else set()
    aceitos = [a for a in aceitos if a["id"] not in removidos]
    if not l or l["fonte"] != "pessoa":
        return {"itens": aceitos, "explicacoes": {}, "fonte": "geometria"}
    por_id = {a["id"]: a for a in aceitos}
    itens = [por_id.pop(i["id"]) for i in l["itens"] if i["id"] in por_id]
    for novo in por_id.values():  # aceito depois da edição: entra pelo km
        km = novo.get("km_na_rota") or 0
        pos = next((n for n, i in enumerate(itens) if (i.get("km_na_rota") or 0) > km), len(itens))
        itens.insert(pos, novo)
    return {"itens": itens, "explicacoes": {}, "fonte": "pessoa"}
