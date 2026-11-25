"""Eventos de produto e as seis metas do PRD (docs/PRD.md, Objetivos e métricas).

Gravar um evento nunca levanta: se o banco falhar, a viagem, o swipe e a triagem
seguem. `dados` só guarda metadado técnico. A pessoa entra como `usuario`, vindo
do token, nunca do corpo.

As consultas são as do painel `GET /metricas` (PV_ADMIN_TOKEN, no mesmo modelo
de `GET /uso/ia`).
"""
from __future__ import annotations

import logging

from psycopg.types.json import Jsonb

from . import banco

log = logging.getLogger("desvio.metricas")

EVENTOS = (
    "viagem_criada", "primeiro_card", "swipe", "roteiro_montado",
    "roteiro_aberto_mapa", "triagem_concluida", "triagem_pulada",
)
TIPOS_DECISAO = ("bora", "passo", "favorito")
# As metas do PRD, para o painel mostrar o número ao lado do medido.
META_VIAGENS_ATE_ROTEIRO = 0.6
META_ACEITE_MIN = 0.35
META_ACEITE_MAX = 0.5
META_PONTOS_SEGUNDA_VIAGEM = 10
META_ROTEIRO_NO_MAPA = 0.4
META_TRIAGEM_SEM_PULAR = 0.7
PRIMEIROS_CARDS = 20

# Viagens criadas que têm um roteiro montado, sobre as viagens criadas.
_VIAGENS_ATE_ROTEIRO = """
select (select count(distinct viagem) from evento
         where evento = 'viagem_criada' and viagem is not null) as viagens,
       (select count(distinct c.viagem) from evento c
         join evento r on r.viagem = c.viagem and r.evento = 'roteiro_montado'
         where c.evento = 'viagem_criada' and c.viagem is not null) as com_roteiro
"""

# Bora e Favorito sobre todas as decisões registradas.
_ACEITE = """
select count(*) filter (where dados->>'tipo' in ('bora', 'favorito')) as aceitos,
       count(*) as swipes
  from evento
 where evento = 'swipe'
"""

# Aceite nos 20 primeiros cards da 1ª viagem menos o da 2ª, por pessoa.
# `ordem` é a posição da decisão na viagem (0 é a primeira). O delta sai em
# fração; o painel converte para pontos percentuais.
_ACEITE_SEGUNDA_VIAGEM = """
with numeradas as (
  select usuario, viagem,
         row_number() over (partition by usuario order by criado_em, id) as n
    from evento
   where evento = 'viagem_criada' and viagem is not null
),
par as (
  select a.usuario, a.viagem as primeira, b.viagem as segunda
    from numeradas a
    join numeradas b on b.usuario = a.usuario and b.n = 2
   where a.n = 1
),
taxas as (
  select p.usuario,
         avg((e.dados->>'tipo' in ('bora', 'favorito'))::int)
           filter (where e.viagem = p.primeira) as t1,
         avg((e.dados->>'tipo' in ('bora', 'favorito'))::int)
           filter (where e.viagem = p.segunda) as t2
    from par p
    join evento e on e.evento = 'swipe' and e.usuario = p.usuario
     and e.viagem in (p.primeira, p.segunda)
     and (e.dados->>'ordem') ~ '^[0-9]+$'
     and (e.dados->>'ordem')::int < %s
   group by p.usuario
)
select count(*) filter (where t1 is not null and t2 is not null) as pessoas,
       avg(t2 - t1) filter (where t1 is not null and t2 is not null) as delta
  from taxas
"""

# Roteiros montados que alguém abriu no mapa.
_ROTEIRO_NO_MAPA = """
select (select count(distinct viagem) from evento
         where evento = 'roteiro_montado' and viagem is not null) as roteiros,
       (select count(distinct m.viagem) from evento m
         join evento a on a.viagem = m.viagem and a.evento = 'roteiro_aberto_mapa'
         where m.evento = 'roteiro_montado' and m.viagem is not null) as abertos
"""

# Um tempo por viagem: o do app (quando a pessoa viu o card), senão o do servidor.
_TEMPO_PRIMEIRO_CARD = """
select count(*) as amostras,
       avg(tempo) as media_ms,
       percentile_cont(0.5) within group (order by tempo) as mediana_ms
  from (
    select distinct on (viagem) (dados->>'tempo_ms')::float as tempo
      from evento
     where evento = 'primeiro_card' and viagem is not null
       and (dados->>'tempo_ms') ~ '^[0-9]+$'
     order by viagem, (dados->>'origem' = 'app') desc, criado_em
  ) t
"""

# Triagens que terminaram com resumo, sobre as que terminaram (concluída ou pulada).
_TRIAGEM_SEM_PULAR = """
select count(*) filter (where evento = 'triagem_concluida') as concluidas,
       count(*) filter (where evento = 'triagem_pulada') as puladas
  from evento
 where evento in ('triagem_concluida', 'triagem_pulada')
"""


def _dados_limpos(evento: str, dados: dict) -> dict:
    """Só as chaves técnicas de cada evento. O resto (e-mail, nome, texto) sai."""
    if evento == "swipe":
        limpo = {}
        if dados.get("tipo") in TIPOS_DECISAO:
            limpo["tipo"] = dados["tipo"]
        ordem = dados.get("ordem")
        if isinstance(ordem, int) and not isinstance(ordem, bool) and ordem >= 0:
            limpo["ordem"] = ordem
        return limpo
    if evento == "primeiro_card":
        limpo = {}
        if dados.get("origem") in ("app", "servidor"):
            limpo["origem"] = dados["origem"]
        tempo = dados.get("tempo_ms")
        if isinstance(tempo, int) and not isinstance(tempo, bool) and tempo >= 0:
            limpo["tempo_ms"] = tempo
        return limpo
    if evento == "roteiro_aberto_mapa" and dados.get("app") in ("google", "waze"):
        return {"app": dados["app"]}
    return {}


def _gravar(usuario: str, evento: str, viagem: str | None, dados: dict) -> None:
    if evento not in EVENTOS:
        return
    with banco.conectar() as con:
        limpo = _dados_limpos(evento, dados)
        if evento == "swipe" and viagem and "ordem" not in limpo:
            n = con.execute("select count(*) as n from evento where usuario = %s and viagem = %s and evento = 'swipe'",
                            (usuario, viagem)).fetchone()["n"]
            limpo["ordem"] = n
        con.execute("insert into evento (usuario, viagem, evento, dados) values (%s, %s, %s, %s)",
                    (usuario, viagem, evento, Jsonb(limpo)))


def registrar(usuario: str, evento: str, viagem: str | None = None, dados: dict | None = None) -> None:
    """Grava o evento. Qualquer falha vira aviso no log e a requisição de quem chamou segue."""
    try:
        _gravar(usuario, evento, viagem, dados or {})
    except Exception:
        log.warning("não consegui registrar o evento %s", evento, exc_info=True)


def _tem_card(resultado: dict) -> bool:
    return any(p.get("cards") for p in (resultado.get("paradas") or []) if isinstance(p, dict))


def primeiro_card_servidor(usuario: str | None, viagem: str | None, job_id: str, resultado: dict) -> None:
    """Uma vez por viagem, quando a busca tem o primeiro card. O tempo sai do relógio do job."""
    if not usuario or not viagem or not _tem_card(resultado):
        return
    try:
        with banco.conectar() as con:
            if con.execute("select 1 from evento where viagem = %s and evento = 'primeiro_card' "
                           "and dados->>'origem' = 'servidor'", (viagem,)).fetchone():
                return
            ms = con.execute("select (extract(epoch from (clock_timestamp() - criado_em)) * 1000)::int as ms "
                             "from jobs where id = %s", (job_id,)).fetchone()
            dados: dict = {"origem": "servidor"}
            if ms and isinstance(ms["ms"], int) and ms["ms"] >= 0:
                dados["tempo_ms"] = ms["ms"]
            con.execute("insert into evento (usuario, viagem, evento, dados) values (%s, %s, 'primeiro_card', %s)",
                        (usuario, viagem, Jsonb(dados)))
    except Exception:
        log.warning("não consegui registrar o primeiro card", exc_info=True)


def _taxa(parte: int, total: int) -> float | None:
    return round(parte / total, 4) if total else None


def _ms(valor) -> int | None:
    return round(valor) if valor is not None else None


def painel() -> dict:
    """As seis metas, com o medido e o alvo do PRD. Sem amostra, a taxa fica null."""
    with banco.conectar() as con:
        v = con.execute(_VIAGENS_ATE_ROTEIRO).fetchone()
        a = con.execute(_ACEITE).fetchone()
        s = con.execute(_ACEITE_SEGUNDA_VIAGEM, (PRIMEIROS_CARDS,)).fetchone()
        m = con.execute(_ROTEIRO_NO_MAPA).fetchone()
        t = con.execute(_TEMPO_PRIMEIRO_CARD).fetchone()
        g = con.execute(_TRIAGEM_SEM_PULAR).fetchone()
    return {
        "viagens_ate_roteiro": {"taxa": _taxa(v["com_roteiro"], v["viagens"]), "meta": META_VIAGENS_ATE_ROTEIRO,
                                "viagens": v["viagens"], "com_roteiro": v["com_roteiro"]},
        "aceite": {"taxa": _taxa(a["aceitos"], a["swipes"]), "meta_min": META_ACEITE_MIN,
                   "meta_max": META_ACEITE_MAX, "aceitos": a["aceitos"], "swipes": a["swipes"]},
        "aceite_segunda_viagem": {
            "pontos": round(s["delta"] * 100, 1) if s["delta"] is not None else None,
            "meta_pontos": META_PONTOS_SEGUNDA_VIAGEM, "pessoas": s["pessoas"]},
        "roteiro_no_mapa": {"taxa": _taxa(m["abertos"], m["roteiros"]), "meta": META_ROTEIRO_NO_MAPA,
                            "abertos": m["abertos"], "roteiros": m["roteiros"]},
        "tempo_primeiro_card": {"media_ms": _ms(t["media_ms"]), "mediana_ms": _ms(t["mediana_ms"]),
                                "amostras": t["amostras"]},
        "triagem_sem_pular": {"taxa": _taxa(g["concluidas"], g["concluidas"] + g["puladas"]),
                              "meta": META_TRIAGEM_SEM_PULAR,
                              "concluidas": g["concluidas"], "puladas": g["puladas"]},
    }
