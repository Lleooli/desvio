"""Geocodificação, rota por terra e utilidades geográficas.

Tudo gratuito e sem chave de API:
- Nominatim (OpenStreetMap) para transformar "Alegrete, RS" em coordenadas
- OSRM para calcular a rota: perfil de carro para carro e moto, perfil de
  bicicleta (servidor da FOSSGIS) para bicicleta
Os servidores públicos têm política de uso justo (Nominatim: 1 req/s, sem uso
pesado). Para produção, suba os seus (infra/osm/README.md) e aponte PV_OSRM_URL,
PV_OSRM_BIKE_URL e PV_NOMINATIM_URL; no Nominatim próprio, PV_NOMINATIM_INTERVALO=0
tira a espera entre as chamadas.
"""
from __future__ import annotations

import asyncio
import math
import os

import httpx

from . import cache

USER_AGENT = os.getenv("PV_USER_AGENT", "planejador-viagem/0.1 (troque-pelo-seu-email@exemplo.com)")
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"}
NOMINATIM_PUBLICO = "https://nominatim.openstreetmap.org"
NOMINATIM = os.getenv("PV_NOMINATIM_URL", NOMINATIM_PUBLICO)
OSRM = os.getenv("PV_OSRM_URL", "https://router.project-osrm.org")
OSRM_BIKE = os.getenv("PV_OSRM_BIKE_URL", "https://routing.openstreetmap.de/routed-bike")


def _intervalo_nominatim(texto: str, url: str) -> float:
    """Segundos entre chamadas ao Nominatim. Aceita "1,1"; valor inválido vira 1,1.

    No servidor público nunca fica abaixo de 1 s (1 req/s, senão o IP é bloqueado).
    """
    try:
        valor = float(texto.replace(",", "."))
    except ValueError:
        valor = 1.1
    if "nominatim.openstreetmap.org" in url:
        valor = max(valor, 1.0)
    return max(valor, 0.0)


# Segundos de espera depois de cada chamada ao Nominatim. 1,1 respeita o servidor público (1 req/s).
NOMINATIM_INTERVALO = _intervalo_nominatim(os.getenv("PV_NOMINATIM_INTERVALO", "1.1"), NOMINATIM)

VEICULOS = ("carro", "moto", "bicicleta")  # moto usa a rota de carro

Ponto = tuple[float, float]  # (lat, lon)


class ErroConhecido(ValueError):
    """Erro que a pessoa entende; a mensagem vai como está para o app."""


class LugarNaoEncontrado(ErroConhecido):
    def __init__(self, lugar: str):
        self.lugar = lugar
        super().__init__(f"Não achamos {lugar}. Confira o nome da cidade e a UF.")


class RotaNaoEncontrada(ErroConhecido):
    def __init__(self, motivo: str = ""):
        self.motivo = motivo  # vai só para o log
        super().__init__("Não achamos uma rota entre essas cidades.")

_cache: dict[str, dict] = {}
_trava_nominatim = asyncio.Lock()


async def _nominatim(client: httpx.AsyncClient, caminho: str, params: dict) -> object:
    """Chamada ao Nominatim, uma por vez, com NOMINATIM_INTERVALO segundos entre elas."""
    chave = caminho + repr(sorted(params.items()))
    if chave in _cache:
        return _cache[chave]
    guardado = cache.obter("nominatim|" + chave)  # 30 dias, entre usuários e reinícios
    if guardado is not None:
        _cache[chave] = guardado
        return guardado
    async with _trava_nominatim:
        r = await client.get(f"{NOMINATIM}/{caminho}", params=params, headers=HEADERS, timeout=30)
        if NOMINATIM_INTERVALO > 0:
            await asyncio.sleep(NOMINATIM_INTERVALO)
    r.raise_for_status()
    _cache[chave] = r.json()
    cache.guardar("nominatim|" + chave, _cache[chave])
    return _cache[chave]


async def geocodificar(client: httpx.AsyncClient, lugar: str) -> dict:
    dados = await _nominatim(client, "search", {"q": lugar, "format": "jsonv2", "limit": 1, "addressdetails": 1})
    if not dados:
        raise LugarNaoEncontrado(lugar)
    d = dados[0]
    end = d.get("address", {})
    return {
        "nome": end.get("city") or end.get("town") or end.get("village") or lugar,
        "uf": _uf(end),
        "lat": float(d["lat"]),
        "lon": float(d["lon"]),
        "exibicao": d.get("display_name"),
    }


async def cidade_e_uf(client: httpx.AsyncClient, ponto: Ponto) -> tuple[str | None, str | None]:
    """Geocodificação reversa no nível de município."""
    d = await _nominatim(client, "reverse", {"lat": ponto[0], "lon": ponto[1], "format": "jsonv2", "zoom": 10, "addressdetails": 1})
    end = (d or {}).get("address", {}) if isinstance(d, dict) else {}
    nome = end.get("city") or end.get("town") or end.get("municipality") or end.get("village")
    return nome, _uf(end)


def _uf(endereco: dict) -> str | None:
    iso = endereco.get("ISO3166-2-lvl4", "")  # ex.: "BR-RS"
    return iso.split("-")[-1] if iso.startswith("BR-") else endereco.get("state")


def servidor_rota(veiculo: str) -> str:
    if veiculo not in VEICULOS:
        raise ValueError(f"Veículo desconhecido: {veiculo}")
    return OSRM_BIKE if veiculo == "bicicleta" else OSRM


async def rota(client: httpx.AsyncClient, origem: Ponto, destino: Ponto, veiculo: str = "carro") -> dict:
    (la1, lo1), (la2, lo2) = origem, destino
    perfil = "bike" if veiculo == "bicicleta" else "driving"
    url = f"{servidor_rota(veiculo)}/route/v1/{perfil}/{lo1},{la1};{lo2},{la2}"
    chave = f"osrm|{veiculo}|{lo1:.4f},{la1:.4f};{lo2:.4f},{la2:.4f}"
    guardada = cache.obter(chave)
    if guardada is not None:
        return {**guardada, "pontos": [tuple(p) for p in guardada["pontos"]]}
    r = await client.get(url, params={"overview": "full", "geometries": "geojson"}, headers=HEADERS, timeout=60)
    r.raise_for_status()
    dados = r.json()
    if dados.get("code") != "Ok" or not dados.get("routes"):
        raise RotaNaoEncontrada(str(dados.get("message") or dados.get("code")))
    rota = dados["routes"][0]
    pontos = [(lat, lon) for lon, lat in rota["geometry"]["coordinates"]]
    resultado = {
        "distancia_km": rota["distance"] / 1000,
        "duracao_h": rota["duration"] / 3600,
        "pontos": pontos,
    }
    cache.guardar(chave, resultado)
    return resultado


def distancia_km(a: Ponto, b: Ponto) -> float:
    """Distância em linha reta (haversine)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def acumuladas(pontos: list[Ponto]) -> list[float]:
    acc = [0.0]
    for a, b in zip(pontos, pontos[1:]):
        acc.append(acc[-1] + distancia_km(a, b))
    return acc


def amostrar(pontos: list[Ponto], intervalo_km: float) -> list[tuple[float, Ponto]]:
    """Pontos a cada `intervalo_km` ao longo da rota: [(km, (lat, lon)), ...]."""
    acc = acumuladas(pontos)
    total = acc[-1]
    res, alvo, i = [], intervalo_km, 1
    while alvo < total:
        while acc[i] < alvo:
            i += 1
        a, b = pontos[i - 1], pontos[i]
        seg = acc[i] - acc[i - 1]
        f = (alvo - acc[i - 1]) / seg if seg else 0.0
        res.append((alvo, (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)))
        alvo += intervalo_km
    return res


def km_na_rota(pontos: list[Ponto], acc: list[float], p: Ponto) -> float:
    """Em que km da rota fica o ponto mais próximo de `p` (para ordenar as paradas)."""
    coslat = math.cos(math.radians(p[0]))
    melhor_i, melhor_d = 0, float("inf")
    for i, (la, lo) in enumerate(pontos):
        d = (la - p[0]) ** 2 + ((lo - p[1]) * coslat) ** 2
        if d < melhor_d:
            melhor_i, melhor_d = i, d
    return acc[melhor_i]


def simplificar(pontos: list[Ponto], maximo: int = 600) -> list[Ponto]:
    """Reduz a polilinha para o front-end desenhar no mapa."""
    if len(pontos) <= maximo:
        return pontos
    passo = len(pontos) / (maximo - 1)
    return [pontos[int(i * passo)] for i in range(maximo - 1)] + [pontos[-1]]
