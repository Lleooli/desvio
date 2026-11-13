"""Dados da pessoa (LGPD, issue #40): exportar tudo em JSON e apagar a conta.

Apagar a conta tem duas partes:
1. Os dados no schema public (usuario, e em cascata viagens, paradas, decisões e
   roteiros; mais os jobs da fila) somem na hora, numa transação, junto com o
   registro em `exclusao_pendente`.
2. A linha em auth.users só sai pela Admin API do Supabase, com a chave
   service_role (SUPABASE_SERVICE_ROLE_KEY, que só existe no servidor). Se a
   chamada dá certo, o registro pendente sai. Se falha, ele fica, e o worker tenta
   de novo (`completar_pendentes`) até conseguir; a política promete até 15 dias.

Enquanto a exclusão está pendente, o token antigo responde 401 (banco.garantir_usuario).
`lugar` e `cache` não são dados pessoais (são os lugares e as rotas, compartilhados)
e ficam.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx

from . import banco, preferencias

log = logging.getLogger("desvio.conta")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
CONFIRMACAO = "APAGAR"
_transporte: httpx.BaseTransport | None = None  # os testes trocam por um httpx.MockTransport


# --- Exportar ----------------------------------------------------------------

def exportar(usuario: str) -> dict:
    """Tudo o que é da pessoa: conta, perfil de gosto, viagens (com paradas, cards e roteiro) e decisões."""
    with banco.conectar() as con:
        u = con.execute("select email, provedor, perfil_gosto, tema, criado_em from usuario where id = %s",
                        (usuario,)).fetchone()
        viagens = con.execute(
            "select v.id, v.origem, v.destino, v.veiculo, v.intervalo_km, v.categorias, v.status, "
            "v.criado_em, v.atualizado_em, r.itens as roteiro_itens, r.explicacao as roteiro_explicacao, "
            "r.fonte as roteiro_fonte, r.atualizado_em as roteiro_atualizado_em "
            "from viagem v left join roteiro r on r.viagem = v.id where v.usuario = %s order by v.criado_em desc",
            (usuario,)).fetchall()
        paradas = con.execute(
            "select p.viagem, p.ordem, p.cidade, p.uf, p.km, p.horas_desde_saida from parada p "
            "join viagem v on v.id = p.viagem where v.usuario = %s order by p.viagem, p.ordem",
            (usuario,)).fetchall()
        cards = con.execute(
            "select pl.viagem, pl.parada, l.id, l.dados ->> 'nome' as nome, l.dados ->> 'categoria' as categoria "
            "from parada_lugar pl join viagem v on v.id = pl.viagem join lugar l on l.id = pl.lugar "
            "where v.usuario = %s order by pl.viagem, pl.parada, pl.posicao", (usuario,)).fetchall()
        decisoes = con.execute(
            "select d.lugar, l.dados ->> 'nome' as nome, d.tipo, d.viagem, d.parada, d.card, d.quando "
            "from decisao d join lugar l on l.id = d.lugar where d.usuario = %s order by d.quando",
            (usuario,)).fetchall()
    por_parada: dict[tuple, list[dict]] = {}
    for c in cards:
        por_parada.setdefault((c["viagem"], c["parada"]), []).append(
            {"id": c["id"], "nome": c["nome"], "categoria": c["categoria"]})
    por_viagem: dict = {}
    for p in paradas:
        por_viagem.setdefault(p["viagem"], []).append(
            {"ordem": p["ordem"], "cidade": p["cidade"], "uf": p["uf"], "km": p["km"],
             "horas_desde_saida": p["horas_desde_saida"], "cards": por_parada.get((p["viagem"], p["ordem"]), [])})
    return {
        "exportado_em": datetime.now(timezone.utc).isoformat(),
        "usuario": dict(u) if u else None,
        "perfil": preferencias.perfil(usuario),
        "viagens": [{
            "id": str(v["id"]), "origem": v["origem"], "destino": v["destino"], "veiculo": v["veiculo"],
            "intervalo_km": v["intervalo_km"], "categorias": v["categorias"], "status": v["status"],
            "criado_em": v["criado_em"], "atualizado_em": v["atualizado_em"],
            "paradas": por_viagem.get(v["id"], []),
            "roteiro": None if v["roteiro_atualizado_em"] is None else {
                "itens": v["roteiro_itens"], "explicacao": v["roteiro_explicacao"], "fonte": v["roteiro_fonte"],
                "atualizado_em": v["roteiro_atualizado_em"]},
        } for v in viagens],
        "decisoes": [{**d, "viagem": str(d["viagem"]) if d["viagem"] else None} for d in decisoes],
    }


# --- Apagar ------------------------------------------------------------------

def _apagar_no_auth(usuario: str) -> str | None:
    """Pede ao Supabase que apague a conta em auth.users. Devolve None se deu certo, ou o erro."""
    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        return "SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY não configurada"
    try:
        with httpx.Client(transport=_transporte, timeout=10) as client:
            r = client.delete(f"{SUPABASE_URL}/auth/v1/admin/users/{usuario}",
                              headers={"apikey": SERVICE_ROLE_KEY, "Authorization": f"Bearer {SERVICE_ROLE_KEY}"})
    except httpx.HTTPError as e:
        return f"{e.__class__.__name__}: {e}"
    if r.status_code in (200, 204, 404):  # 404: a conta já não existe no Auth
        return None
    return f"HTTP {r.status_code}: {r.text[:200]}"


def _apagar_dados(con, usuario: str) -> None:
    con.execute("delete from jobs where usuario = %s", (usuario,))
    con.execute("delete from usuario where id = %s", (usuario,))  # cascata: viagens, paradas, decisões, roteiros


def _tentar_auth(usuario: str) -> bool:
    erro = _apagar_no_auth(usuario)
    with banco.conectar() as con:
        if erro is None:
            con.execute("delete from exclusao_pendente where usuario = %s", (usuario,))
            return True
        log.warning("exclusão da conta %s no Supabase Auth falhou: %s", usuario, erro)
        con.execute("update exclusao_pendente set tentativas = tentativas + 1, ultimo_erro = %s, "
                    "tentado_em = now() where usuario = %s", (erro, usuario))
    return False


def apagar(usuario: str) -> dict:
    """Apaga os dados da pessoa na hora e a conta no Supabase Auth (ou deixa pendente)."""
    with banco.conectar() as con:
        con.execute("insert into exclusao_pendente (usuario) values (%s) on conflict (usuario) do nothing",
                    (usuario,))
        _apagar_dados(con, usuario)
    return {"dados": "apagados", "conta": "apagada" if _tentar_auth(usuario) else "pendente"}


def completar_pendentes() -> int:
    """Tenta de novo as exclusões que falharam no Supabase Auth (o worker chama). Devolve quantas fechou."""
    with banco.conectar() as con:
        pendentes = [r["usuario"] for r in con.execute(
            "select usuario from exclusao_pendente order by pedido_em").fetchall()]
    feitas = 0
    for u in pendentes:
        u = str(u)
        with banco.conectar() as con:
            _apagar_dados(con, u)  # de novo, por garantia: nada pode ter voltado
        feitas += _tentar_auth(u)
    return feitas
