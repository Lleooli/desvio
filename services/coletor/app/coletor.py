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
import re
import unicodedata

import httpx

from . import geo, gmaps, instagram, osm

CATEGORIAS_PADRAO = ["turismo", "restaurante", "posto"]
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
                       nota_minima: float = 4.0) -> list[dict]:
    """Recebe paradas {nome, uf, lat, lon, raio_km} e devolve as mesmas com "cards"."""
    # 1) Base gratuita e estável: OpenStreetMap
    brutos = []
    for p in paradas:
        brutos.append(await osm.pois(client, (p["lat"], p["lon"]), p["raio_km"], categorias))

    # 2) Google Maps (via gosom): um job só para a viagem inteira
    google: dict[str, list[dict]] = {}
    avisos: list[str] = []
    if usar_google_maps:
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
    await instagram.completar(client, todos, usar_busca=buscar_instagram)

    if avisos:
        for p in paradas:
            p.setdefault("avisos", []).extend(avisos)
    return paradas


async def planejar_carro(origem: str, destino: str, intervalo_km: float = 200,
                         categorias: list[str] | None = None, por_categoria: int = 5,
                         usar_google_maps: bool = False, buscar_instagram: bool = True,
                         raio_parada_km: float = 8, raio_destino_km: float = 15) -> dict:
    categorias = categorias or CATEGORIAS_PADRAO
    async with httpx.AsyncClient() as client:
        o = await geo.geocodificar(client, origem)
        d = await geo.geocodificar(client, destino)
        rota = await geo.rota_carro(client, (o["lat"], o["lon"]), (d["lat"], d["lon"]))
        pontos = rota["pontos"]
        acc = geo.acumuladas(pontos)
        total = acc[-1]

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

        await montar_cards(client, paradas, categorias, por_categoria, usar_google_maps, buscar_instagram)

    for p in paradas:
        p["km_na_rota"] = round(geo.km_na_rota(pontos, acc, (p["lat"], p["lon"])))
        p["horas_desde_saida"] = round(p["km_na_rota"] / total * rota["duracao_h"], 1) if total else 0
        for c in p["cards"]:
            c["km_na_rota"] = round(geo.km_na_rota(pontos, acc, (c["lat"], c["lon"])), 1)
            c["horas_desde_saida"] = round(c["km_na_rota"] / total * rota["duracao_h"], 1) if total else 0

    return {
        "modo": "carro",
        "origem": o, "destino": d,
        "rota": {"distancia_km": round(rota["distancia_km"]), "duracao_h": round(rota["duracao_h"], 1),
                 "polilinha": geo.simplificar(pontos)},
        "paradas": paradas,
    }


async def planejar_cidades(cidades: list[dict], categorias: list[str] | None = None, por_categoria: int = 8,
                           usar_google_maps: bool = False, buscar_instagram: bool = True,
                           raio_km: float = 12) -> dict:
    """Modo avião: cidades de escala/estadia [{"cidade": "Salvador, BA", "dias": 2}, ...]."""
    categorias = categorias or ["turismo", "natureza", "restaurante"]
    async with httpx.AsyncClient() as client:
        paradas = []
        for c in cidades:
            g = await geo.geocodificar(client, c["cidade"])
            paradas.append({"nome": g["nome"], "uf": g["uf"], "lat": g["lat"], "lon": g["lon"],
                            "dias": c.get("dias", 1), "tipo": "estadia", "raio_km": raio_km})
        # mais dias na cidade → mais opções para deslizar
        await montar_cards(client, paradas, categorias,
                           max(por_categoria, por_categoria * max(p["dias"] for p in paradas) // 2),
                           usar_google_maps, buscar_instagram)
    return {"modo": "aviao", "paradas": paradas}
