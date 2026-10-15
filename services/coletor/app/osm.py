"""Dados do OpenStreetMap via Overpass API (gratuito, estável e legal de usar).

Serve como base sempre disponível: cidades no caminho, postos, restaurantes e
atrações. Quando o raspador do Google Maps estiver ligado, ele complementa com
fotos, notas e avaliações.
"""
from __future__ import annotations

import asyncio
import os
import re
from urllib.parse import quote

import httpx

from .geo import HEADERS, Ponto, distancia_km

OVERPASS = os.getenv("PV_OVERPASS_URL", "https://overpass-api.de/api/interpreter")

FILTROS: dict[str, list[str]] = {
    "posto": ['["amenity"="fuel"]'],
    "restaurante": ['["amenity"~"^(restaurant|cafe|fast_food|ice_cream)$"]'],
    "turismo": [
        '["tourism"~"^(attraction|viewpoint|museum|gallery|zoo|theme_park)$"]',
        '["historic"~"^(monument|memorial|castle|ruins|archaeological_site|fort)$"]',
    ],
    "natureza": [
        '["leisure"~"^(park|nature_reserve)$"]',
        '["natural"~"^(beach|waterfall|peak|cave_entrance|hot_spring)$"]',
    ],
    "hospedagem": ['["tourism"~"^(hotel|guest_house|hostel|motel|chalet)$"]'],
}

_RESTAURANTE = {"restaurant", "cafe", "fast_food", "ice_cream"}
_HOSPEDAGEM = {"hotel", "guest_house", "hostel", "motel", "chalet"}


def categoria(tags: dict) -> str | None:
    if tags.get("amenity") == "fuel":
        return "posto"
    if tags.get("amenity") in _RESTAURANTE:
        return "restaurante"
    if tags.get("tourism") in _HOSPEDAGEM:
        return "hospedagem"
    if tags.get("tourism") or tags.get("historic"):
        return "turismo"
    if tags.get("leisure") or tags.get("natural"):
        return "natureza"
    return None


async def _overpass(client: httpx.AsyncClient, consulta: str) -> list[dict]:
    for tentativa in range(4):
        r = await client.post(OVERPASS, data={"data": consulta}, headers=HEADERS, timeout=120)
        if r.status_code in (429, 502, 503, 504):
            await asyncio.sleep(5 * (tentativa + 1))
            continue
        r.raise_for_status()
        return r.json().get("elements", [])
    raise RuntimeError("Overpass indisponível no momento (rate limit). Tente de novo em alguns minutos.")


def _populacao(tags: dict) -> int:
    n = re.sub(r"\D", "", tags.get("population", ""))
    return int(n) if n else 0


async def cidade_proxima(client: httpx.AsyncClient, ponto: Ponto, raio_km: float = 30) -> dict | None:
    """Escolhe a cidade mais interessante perto de um ponto da estrada:
    prefere cidades grandes, mas penaliza a distância até a rota."""
    lat, lon = ponto
    q = (f'[out:json][timeout:30];node(around:{int(raio_km * 1000)},{lat},{lon})'
         f'["place"~"^(city|town)$"]["name"];out body;')
    els = await _overpass(client, q)
    if not els:
        return None

    def nota(e: dict) -> tuple[float, float]:
        d = distancia_km(ponto, (e["lat"], e["lon"]))
        return (_populacao(e.get("tags", {})) / (1 + d), -d)

    e = max(els, key=nota)
    t = e.get("tags", {})
    return {"nome": t["name"], "lat": e["lat"], "lon": e["lon"], "populacao": _populacao(t) or None}


async def pois(client: httpx.AsyncClient, centro: Ponto, raio_km: float, categorias: list[str],
               limite: int = 400) -> list[dict]:
    lat, lon = centro
    raio = int(raio_km * 1000)
    partes = [f'nwr(around:{raio},{lat},{lon}){f}["name"];'
              for cat in categorias for f in FILTROS.get(cat, [])]
    if not partes:
        return []
    q = f'[out:json][timeout:90];({"".join(partes)});out center {limite};'
    res = []
    for e in await _overpass(client, q):
        tags = e.get("tags", {})
        cat = categoria(tags)
        la = e.get("lat", e.get("center", {}).get("lat"))
        lo = e.get("lon", e.get("center", {}).get("lon"))
        if cat not in categorias or la is None:
            continue
        res.append({"osm_id": f'{e["type"]}/{e["id"]}', "nome": tags["name"], "categoria": cat,
                    "lat": la, "lon": lo, "tags": tags})
    return res


def relevancia(p: dict, centro: Ponto) -> float:
    """OSM não tem nota de avaliação; usamos 'quão bem documentado' o lugar é
    como sinal de relevância (Wikipedia, site, Instagram, horário...)."""
    t = p["tags"]
    s = len(t)
    s += 15 if ("wikipedia" in t or "wikidata" in t) else 0
    s += 5 if any(k in t for k in ("website", "contact:website", "contact:instagram", "instagram")) else 0
    s += 3 if "opening_hours" in t else 0
    return s - distancia_km(centro, (p["lat"], p["lon"]))


def instagram_das_tags(tags: dict) -> str | None:
    bruto = tags.get("contact:instagram") or tags.get("instagram")
    if not bruto:
        return None
    m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", bruto)
    handle = (m.group(1) if m else bruto).strip("@/ ")
    return f"https://instagram.com/{handle}" if handle else None


def foto_das_tags(tags: dict) -> str | None:
    img = tags.get("image", "")
    if img.startswith("http"):
        return img
    commons = tags.get("wikimedia_commons", "")
    if commons.startswith("File:"):
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(commons[5:])}?width=800"
    return None


async def resumo_wikipedia(client: httpx.AsyncClient, tag: str) -> tuple[str | None, str | None]:
    """Foto e resumo de um ponto turístico a partir da tag wikipedia ("pt:Nome")."""
    lang, _, titulo = tag.partition(":") if ":" in tag else ("pt", "", tag)
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(titulo.replace(' ', '_'))}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        if r.status_code != 200:
            return None, None
        j = r.json()
        return (j.get("originalimage") or j.get("thumbnail") or {}).get("source"), j.get("extract")
    except httpx.HTTPError:
        return None, None
