"""Orquestra a coleta e devolve "cards" prontos para a tela de swipe.

Formato de um card (o front só precisa disto):
{
  "id": "gmaps:ChIJ..." | "osm:node/123",
  "nome", "categoria" (turismo|restaurante|posto|natureza|hospedagem),
  "cidade", "uf", "lat", "lon",
  "foto", "fotos", "nota", "avaliacoes", "faixa_preco", "descricao",
  "endereco", "site", "telefone", "instagram", "instagram_origem",
  "link_maps", "km_na_rota", "horas_desde_saida", "fonte"
}
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import unicodedata
from collections.abc import Callable

import httpx

from . import geo, gmaps, instagram, osm

log = logging.getLogger("desvio.coletor")

# progresso(etapa, titulo, detalhe, percentual); etapas: rota, cidades, lugares, instagram
Progresso = Callable[[str, str, str, int], None]


def _avisar(progresso: Progresso | None, etapa: str, titulo: str, detalhe: str, percentual: int) -> None:
    if not progresso:
        return
    try:
        progresso(etapa, titulo, detalhe, percentual)
    except Exception:  # mostrar progresso nunca pode derrubar a coleta
        log.warning("não consegui gravar o progresso (%s)", etapa, exc_info=True)


def _numero(n: float) -> str:
    """2731 -> "2.731" (formato brasileiro)."""
    return f"{round(n):,}".replace(",", ".")


def texto_rota(distancia_km: float, duracao_h: float, veiculo: str) -> str:
    de = "de pedal" if veiculo == "bicicleta" else "de estrada"
    horas = "menos de 1h" if duracao_h < 1 else f"uns {_numero(duracao_h)}h"
    return f"{_numero(distancia_km)} km, {horas} {de}"


def texto_cidades(n: int, intervalo_km: float) -> tuple[str, str]:
    if n == 0:
        return "Nenhuma cidade no caminho", "Só o destino"
    titulo = f"{_numero(n)} cidade{'s' if n != 1 else ''} para parar"
    return titulo, f"Uma a cada {_numero(intervalo_km)} km, mais o destino"


CATEGORIAS_PADRAO = ["turismo", "restaurante", "posto"]
# teto de paradas por viagem: 10 km numa viagem de 4.000 km dariam 400 paradas, horas de
# Overpass e Nominatim (1 req/s) e um job do gosom enorme. Acima disso o intervalo cresce.
MAX_PARADAS = int(os.getenv("PV_MAX_PARADAS", "30"))


def intervalo_efetivo(distancia_km: float, intervalo_km: float) -> float:
    """O intervalo pedido, ou o menor que cabe em MAX_PARADAS paradas."""
    return max(intervalo_km, distancia_km / MAX_PARADAS) if MAX_PARADAS > 0 else intervalo_km
CONSULTA_GOOGLE = {
    "turismo": "pontos turísticos",
    "restaurante": "restaurantes",
    "posto": "posto de combustível",
    "natureza": "parques e cachoeiras",
    "hospedagem": "hotéis",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def _card_osm(p: dict, parada: dict) -> dict:
    t = p["tags"]
    rua = " ".join(x for x in (t.get("addr:street"), t.get("addr:housenumber")) if x)
    return {
        "id": "osm:" + p["osm_id"], "fonte": "openstreetmap",
        "nome": p["nome"], "categoria": p["categoria"],
        "cidade": parada["nome"], "uf": parada.get("uf"),
        "lat": p["lat"], "lon": p["lon"],
        "foto": osm.foto_das_tags(t), "fotos": [],
        "nota": None, "avaliacoes": None, "faixa_preco": None,
        "descricao": t.get("description"),
        "endereco": rua or None,
        "site": t.get("website") or t.get("contact:website"),
        "telefone": t.get("phone") or t.get("contact:phone"),
        "instagram": osm.instagram_das_tags(t),
        "wikipedia": t.get("wikipedia"),
        "horarios": t.get("opening_hours"),
        "link_maps": f'https://www.google.com/maps/search/?api=1&query={p["lat"]},{p["lon"]}',
    }


def _card_google(g: dict, cat: str, parada: dict) -> dict:
    chave = g.get("place_id") or hashlib.md5(f'{g["nome"]}{g["lat"]}{g["lon"]}'.encode()).hexdigest()[:16]
    card = {k: v for k, v in g.items() if k not in ("input_id", "place_id", "categoria_google")}
    card.update({"id": "gmaps:" + chave, "fonte": "google_maps", "categoria": cat,
                 "tipo": g.get("categoria_google"), "cidade": parada["nome"], "uf": parada.get("uf")})
    if instagram.handle_de_texto(g.get("site") or ""):
        card["instagram"] = "https://instagram.com/" + instagram.handle_de_texto(g["site"])
        card["instagram_origem"] = "site"
    return card


def _consulta_cidade(cat: str, parada: dict) -> str:
    local = f'{parada["nome"]}, {parada["uf"]}' if parada.get("uf") else parada["nome"]
    return f"{CONSULTA_GOOGLE[cat]} em {local}"


async def montar_cards(client: httpx.AsyncClient, paradas: list[dict], categorias: list[str],
                       por_categoria: int, usar_google_maps: bool, buscar_instagram: bool,
                       nota_minima: float = 4.0, progresso: Progresso | None = None) -> list[dict]:
    """Recebe paradas {nome, uf, lat, lon, raio_km} e devolve as mesmas com "cards"."""
    # 1) Base gratuita e estável: OpenStreetMap
    leva = "leva uns 3 minutos" if usar_google_maps else "leva menos de 1 minuto"
    brutos = []
    for i, p in enumerate(paradas):
        _avisar(progresso, "lugares", "Buscando fotos e notas", f'{p["nome"]} agora · {leva}',
                35 + 40 * i // len(paradas))
        brutos.append(await osm.pois(client, (p["lat"], p["lon"]), p["raio_km"], categorias))

    # 2) Google Maps (via gosom): um job só para a viagem inteira
    google: dict[str, list[dict]] = {}
    avisos: list[str] = []
    if usar_google_maps:
        _avisar(progresso, "lugares", "Buscando fotos e notas", "Google Maps · leva uns 3 minutos", 75)
        consultas = {f"{i}|{cat}": _consulta_cidade(cat, p)
                     for i, p in enumerate(paradas) for cat in categorias if cat in CONSULTA_GOOGLE}
        try:
            google = await gmaps.buscar_lote(client, consultas)
        except (gmaps.GosomIndisponivel, RuntimeError, TimeoutError, httpx.HTTPError) as e:
            avisos.append(f"Google Maps indisponível, usei só OpenStreetMap: {e}")

    # 3) Junta, prioriza e corta por categoria
    for i, p in enumerate(paradas):
        centro = (p["lat"], p["lon"])
        cards: list[dict] = []
        for cat in categorias:
            escolhidos: list[dict] = []
            vistos: set[str] = set()
            candidatos = [g for g in google.get(f"{i}|{cat}", [])
                          if g["lat"] is not None
                          and geo.distancia_km(centro, (g["lat"], g["lon"])) <= p["raio_km"] * 2
                          and (g["nota"] is None or g["nota"] >= nota_minima)
                          and (g.get("status") or "").lower() not in {"closed permanently", "fechado permanentemente"}]
            # nota bayesiana: 4,8 com 5 avaliações não passa na frente de 4,6 com 2.000
            candidatos.sort(key=lambda g: -((g["nota"] or 0) * (g["avaliacoes"] or 0) + 4.2 * 30) / ((g["avaliacoes"] or 0) + 30))
            for g in candidatos[:por_categoria]:
                escolhidos.append(_card_google(g, cat, p))
                vistos.add(_norm(g["nome"]))
            osm_cat = sorted((x for x in brutos[i] if x["categoria"] == cat), key=lambda x: -osm.relevancia(x, centro))
            for x in osm_cat:
                if len(escolhidos) >= por_categoria:
                    break
                if _norm(x["nome"]) not in vistos:
                    escolhidos.append(_card_osm(x, p))
                    vistos.add(_norm(x["nome"]))
            cards.extend(escolhidos)
        p["cards"] = cards

    todos = [c for p in paradas for c in p["cards"]]

    # 4) Fotos e resumos da Wikipedia para atrações do OSM sem foto
    sem_foto = [c for c in todos if not c.get("foto") and c.get("wikipedia")]
    for c, (foto, resumo) in zip(sem_foto, await asyncio.gather(
            *(osm.resumo_wikipedia(client, c["wikipedia"]) for c in sem_foto))):
        c["foto"] = c["foto"] or foto
        c["descricao"] = c.get("descricao") or resumo

    # 5) Instagram dos restaurantes
    restaurantes = sum(1 for c in todos if c.get("categoria") == "restaurante")
    _avisar(progresso, "instagram", "Instagram dos restaurantes",
            f"{restaurantes} restaurante{'s' if restaurantes != 1 else ''}", 90)
    await instagram.completar(client, todos, usar_busca=buscar_instagram)

    if avisos:
        for p in paradas:
            p.setdefault("avisos", []).extend(avisos)
    return paradas


async def planejar_viagem(origem: str, destino: str, intervalo_km: float = 200,
                          categorias: list[str] | None = None, por_categoria: int = 5,
                          usar_google_maps: bool = False, buscar_instagram: bool = True,
                          veiculo: str = "carro",
                          raio_parada_km: float = 8, raio_destino_km: float = 15,
                          progresso: Progresso | None = None) -> dict:
    """Viagem por terra (carro, moto ou bicicleta) com paradas a cada `intervalo_km`.

    `progresso` recebe as etapas na ordem: rota, cidades, lugares, instagram.
    """
    categorias = categorias or CATEGORIAS_PADRAO
    async with httpx.AsyncClient() as client:
        o = await geo.geocodificar(client, origem)
        d = await geo.geocodificar(client, destino)
        rota = await geo.rota(client, (o["lat"], o["lon"]), (d["lat"], d["lon"]), veiculo)
        pontos = rota["pontos"]
        acc = geo.acumuladas(pontos)
        total = acc[-1]
        intervalo_km = intervalo_efetivo(total, intervalo_km)
        _avisar(progresso, "rota", "Rota calculada",
                texto_rota(rota["distancia_km"], rota["duracao_h"], veiculo), 20)

        paradas: list[dict] = []
        vistas = {_norm(o["nome"]), _norm(d["nome"])}
        for km, ponto in geo.amostrar(pontos, intervalo_km):
            if total - km < intervalo_km * 0.5:
                break  # muito perto do destino, que já entra separado
            cidade = await osm.cidade_proxima(client, ponto)
            if not cidade or _norm(cidade["nome"]) in vistas:
                continue
            vistas.add(_norm(cidade["nome"]))
            _, uf = await geo.cidade_e_uf(client, (cidade["lat"], cidade["lon"]))
            paradas.append({**cidade, "uf": uf, "tipo": "parada", "raio_km": raio_parada_km})
        paradas.append({"nome": d["nome"], "uf": d["uf"], "lat": d["lat"], "lon": d["lon"],
                        "tipo": "destino", "raio_km": raio_destino_km})
        _avisar(progresso, "cidades", *texto_cidades(len(paradas) - 1, intervalo_km), 35)

        await montar_cards(client, paradas, categorias, por_categoria, usar_google_maps, buscar_instagram,
                           progresso=progresso)

    for p in paradas:
        p["km_na_rota"] = round(geo.km_na_rota(pontos, acc, (p["lat"], p["lon"])))
        p["horas_desde_saida"] = round(p["km_na_rota"] / total * rota["duracao_h"], 1) if total else 0
        for c in p["cards"]:
            c["km_na_rota"] = round(geo.km_na_rota(pontos, acc, (c["lat"], c["lon"])), 1)
            c["horas_desde_saida"] = round(c["km_na_rota"] / total * rota["duracao_h"], 1) if total else 0

    return {
        "veiculo": veiculo,
        "intervalo_km": round(intervalo_km, 1),
        "origem": o, "destino": d,
        "rota": {"distancia_km": round(rota["distancia_km"]), "duracao_h": round(rota["duracao_h"], 1),
                 "polilinha": geo.simplificar(pontos)},
        "paradas": paradas,
    }
