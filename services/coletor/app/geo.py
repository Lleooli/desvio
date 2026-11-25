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

from . import cache, cidades, fronteira

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
    # "Cidade, UF" que veio do autocompletar já está na lista do IBGE: nem chama o Nominatim
    local = cidades.exata(lugar)
    if local:
        return {"nome": local["nome"], "uf": local["uf"], "lat": local["lat"], "lon": local["lon"],
                "exibicao": local["rotulo"]}
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


async def cidade_uf_pais(client: httpx.AsyncClient, ponto: Ponto) -> tuple[str | None, str | None, str | None]:
    """Geocodificação reversa no nível de município: nome, UF e país ("br"; None se não veio)."""
    d = await _nominatim(client, "reverse", {"lat": ponto[0], "lon": ponto[1], "format": "jsonv2", "zoom": 10, "addressdetails": 1})
    end = (d or {}).get("address", {}) if isinstance(d, dict) else {}
    nome = end.get("city") or end.get("town") or end.get("municipality") or end.get("village")
    return nome, _uf(end), (end.get("country_code") or "").lower() or None


async def cidade_e_uf(client: httpx.AsyncClient, ponto: Ponto) -> tuple[str | None, str | None]:
    """Geocodificação reversa no nível de município."""
    nome, uf, _ = await cidade_uf_pais(client, ponto)
    return nome, uf


def _uf(endereco: dict) -> str | None:
    iso = endereco.get("ISO3166-2-lvl4", "")  # ex.: "BR-RS"
    return iso.split("-")[-1] if iso.startswith("BR-") else endereco.get("state")


def servidor_rota(veiculo: str) -> str:
    if veiculo not in VEICULOS:
        raise ValueError(f"Veículo desconhecido: {veiculo}")
    return OSRM_BIKE if veiculo == "bicicleta" else OSRM


# Quantas vezes a rota tenta um ponto de passagem no Brasil antes de desistir (cada uma é
# uma chamada a mais ao OSRM)
MAX_PASSAGENS = 3


async def _rotas_osrm(client: httpx.AsyncClient, pontos: list[Ponto], veiculo: str) -> list[dict]:
    """As rotas do OSRM pelos `pontos`, a mais rápida primeiro; com 2 pontos, com alternativas."""
    perfil = "bike" if veiculo == "bicicleta" else "driving"
    coords = ";".join(f"{lo},{la}" for la, lo in pontos)
    params = {"overview": "full", "geometries": "geojson"}
    if len(pontos) == 2:  # o OSRM só calcula alternativas entre dois pontos
        params["alternatives"] = "3"
    r = await client.get(f"{servidor_rota(veiculo)}/route/v1/{perfil}/{coords}", params=params,
                         headers=HEADERS, timeout=60)
    r.raise_for_status()
    dados = r.json()
    if dados.get("code") != "Ok" or not dados.get("routes"):
        raise RotaNaoEncontrada(str(dados.get("message") or dados.get("code")))
    return [{"distancia_km": x["distance"] / 1000, "duracao_h": x["duration"] / 3600,
             "pontos": [(lat, lon) for lon, lat in x["geometry"]["coordinates"]]}
            for x in dados["routes"]]


async def _rota_no_brasil(client: httpx.AsyncClient, origem: Ponto, destino: Ponto, veiculo: str) -> dict:
    """A rota mais rápida que não sai do Brasil (issue #95).

    O OSRM vai pelo caminho mais curto, mesmo que passe por outro país: de Alegrete a
    Vitória da Conquista ele foi por Hohenau e Ciudad del Este. Primeiro vale a mais
    rápida das alternativas que fica no Brasil. Se nenhuma fica, a rota passa pela sede
    de município brasileira mais perto do trecho de fora (fronteira.ponto_de_passagem),
    até MAX_PASSAGENS vezes. Se mesmo assim sair, fica a mais rápida, com
    `sai_do_brasil`, e as paradas fora do país são descartadas pelo coletor.
    """
    rotas = await _rotas_osrm(client, [origem, destino], veiculo)
    if not (fronteira.no_brasil(origem) and fronteira.no_brasil(destino)):
        return rotas[0]  # viagem que começa ou termina fora: a regra não se aplica
    for r in rotas:
        if not fronteira.pontos_fora(r["pontos"]):
            return r
    passagens: list[Ponto] = []
    fora = fronteira.pontos_fora(rotas[0]["pontos"])
    for _ in range(MAX_PASSAGENS):
        via = fronteira.ponto_de_passagem(fora)
        if via is None or via in passagens:
            break
        passagens.append(via)
        passagens.sort(key=lambda p: distancia_km(origem, p))
        try:
            [r, *_] = await _rotas_osrm(client, [origem, *passagens, destino], veiculo)
        except (RotaNaoEncontrada, httpx.HTTPError):
            break
        fora = fronteira.pontos_fora(r["pontos"])
        if not fora:
            return r
    return {**rotas[0], "sai_do_brasil": True}


async def rota(client: httpx.AsyncClient, origem: Ponto, destino: Ponto, veiculo: str = "carro") -> dict:
    (la1, lo1), (la2, lo2) = origem, destino
    servidor_rota(veiculo)  # veículo desconhecido falha antes do cache
    # "osrm-br": a rota agora fica no Brasil; as guardadas com "osrm|" podiam passar pelo Paraguai
    chave = f"osrm-br|{veiculo}|{lo1:.4f},{la1:.4f};{lo2:.4f},{la2:.4f}"
    guardada = cache.obter(chave)
    if guardada is not None:
        return {**guardada, "pontos": [tuple(p) for p in guardada["pontos"]]}
    resultado = await _rota_no_brasil(client, origem, destino, veiculo)
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
