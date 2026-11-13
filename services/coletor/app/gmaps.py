"""Única porta para o Google Maps. Duas fontes, escolhidas por configuração:

- **places** (produção): a Places API (New) oficial, por `httpx`. Uma Text Search
  por consulta, com um field mask mínimo (veja CAMPOS_PLACES e o SKU que ele cobra).
- **gosom** (protótipo): o gosom/google-maps-scraper (open source, MIT) em Docker.
  Raspar viola os termos do Google; serve só para desenvolvimento.

    docker run -p 8080:8080 -v "$PWD/gmapsdata:/gmapsdata" \\
        gosom/google-maps-scraper -data-folder /gmapsdata

`PV_GOOGLE_FONTE=places|gosom` escolhe a fonte. Sem ela, vale `places` quando há
`PV_GOOGLE_PLACES_KEY` e `gosom` quando não há. A chave só existe no servidor.

As duas fontes devolvem o mesmo formato de lugar. No gosom, todas as buscas da
viagem vão num job só; cada busca leva um ID próprio (sintaxe "consulta #!#id"),
e assim cada resultado volta marcado com a parada e a categoria a que pertence.

Fotos da Places API: o card leva a URL do endpoint `/fotos/...` da nossa API,
assinada com HMAC (`url_foto`). O endpoint troca o nome da foto pela URL da
imagem no Google (`url_da_foto`) e redireciona; a chave nunca chega ao app.
Os autores de cada foto vão em `fotos_autores`, para o app mostrar a atribuição.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import re
import uuid

import httpx

log = logging.getLogger("desvio.gmaps")

GOSOM_URL = os.getenv("PV_GOSOM_URL", "http://localhost:8080")
PLACES_URL = "https://places.googleapis.com/v1"

# Field mask da Text Search (New). O Google cobra o SKU do campo mais caro pedido:
# rating, userRatingCount, priceLevel, priceRange, websiteUri, nationalPhoneNumber e
# regularOpeningHours são "Text Search Enterprise"; o resto é "Pro". Nada de
# Atmosphere (editorialSummary, reviews, allowsDogs…), que custa mais.
CAMPOS_PLACES = ",".join("places." + c for c in (
    "id", "displayName", "formattedAddress", "location", "primaryTypeDisplayName",
    "googleMapsUri", "photos", "businessStatus",
    "rating", "userRatingCount", "priceLevel", "priceRange", "websiteUri",
    "nationalPhoneNumber", "regularOpeningHours.weekdayDescriptions",
))
LARGURA_FOTO = 800
MAX_FOTOS = 6
BUSCAS_SIMULTANEAS = 5
TIMEOUT_PLACES_S = 15
_NOME_FOTO = re.compile(r"^places/[A-Za-z0-9_-]+/photos/[A-Za-z0-9_-]+$")


class GoogleIndisponivel(RuntimeError):
    """O Google não respondeu: fonte fora do ar, sem chave ou todas as buscas falharam."""


GosomIndisponivel = GoogleIndisponivel  # nome antigo, mantido para quem já usa


def _chave_places() -> str:
    return os.getenv("PV_GOOGLE_PLACES_KEY", "").strip()


def fonte() -> str:
    """"places" ou "gosom", lido a cada chamada (PV_GOOGLE_FONTE ou, sem ela, pela chave)."""
    escolhida = os.getenv("PV_GOOGLE_FONTE", "").strip().lower()
    if escolhida in ("places", "gosom"):
        return escolhida
    return "places" if _chave_places() else "gosom"


async def buscar_lote(client: httpx.AsyncClient, consultas: dict[str, str], *, lang: str = "pt",
                      depth: int = 1, max_time_s: int = 600, intervalo_s: int = 10,
                      espera_max_s: int = 1800) -> dict[str, list[dict]]:
    """Recebe {id: "restaurantes em Lages, SC", ...} e devolve {id: [lugares]}.

    Na Places API, uma consulta que falhou fica de fora da resposta (assim o cache
    não guarda uma lista vazia por 30 dias); se todas falharem, GoogleIndisponivel.
    """
    if not consultas:
        return {}
    if fonte() == "places":
        return await _buscar_lote_places(client, consultas)
    return await _buscar_lote_gosom(client, consultas, lang=lang, depth=depth, max_time_s=max_time_s,
                                    intervalo_s=intervalo_s, espera_max_s=espera_max_s)


# ---------------------------------------------------------------- Places API (New)

def _assinatura(nome: str, largura: int) -> str:
    segredo = ("desvio-fotos|" + _chave_places()).encode()
    return hmac.new(segredo, f"{nome}|{largura}".encode(), hashlib.sha256).hexdigest()[:32]


def url_foto(nome: str, largura: int = LARGURA_FOTO) -> str:
    """URL do nosso endpoint /fotos para uma foto da Places API, assinada.

    Com PV_API_URL_PUBLICA, a URL é absoluta; sem ela, relativa à API (o app junta a base).
    """
    base = os.getenv("PV_API_URL_PUBLICA", "").strip().rstrip("/")
    return f"{base}/fotos/{nome}?l={largura}&ass={_assinatura(nome, largura)}"


def foto_valida(nome: str, largura: int, assinatura: str) -> bool:
    """Só fotos que o coletor assinou passam: o endpoint não vira um proxy aberto (e pago)."""
    if not _chave_places() or not _NOME_FOTO.match(nome or ""):
        return False
    return hmac.compare_digest(_assinatura(nome, largura), assinatura or "")


async def url_da_foto(client: httpx.AsyncClient, nome: str, largura: int = LARGURA_FOTO) -> str | None:
    """Troca o nome da foto (places/X/photos/Y) pela URL da imagem no Google, sem a chave.

    Usa skipHttpRedirect=true: o Google devolve {"photoUri"} em vez da imagem.
    Erro ou foto vencida: None (o app mostra o card sem foto).
    """
    try:
        r = await client.get(f"{PLACES_URL}/{nome}/media",
                             params={"maxWidthPx": largura, "skipHttpRedirect": "true"},
                             headers={"X-Goog-Api-Key": _chave_places()}, timeout=TIMEOUT_PLACES_S)
        r.raise_for_status()
        return r.json().get("photoUri") or None
    except (httpx.HTTPError, ValueError):
        log.warning("não consegui a foto %s da Places API", nome, exc_info=True)
        return None


_STATUS = {"CLOSED_PERMANENTLY": "Fechado permanentemente", "CLOSED_TEMPORARILY": "Fechado temporariamente"}
_NIVEL_PRECO = {"PRICE_LEVEL_INEXPENSIVE": "$", "PRICE_LEVEL_MODERATE": "$$",
                "PRICE_LEVEL_EXPENSIVE": "$$$", "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$"}
_MOEDA = {"BRL": "R$", "USD": "US$", "EUR": "€"}


def _faixa_preco(lugar: dict) -> str | None:
    faixa = lugar.get("priceRange") or {}
    ini, fim = faixa.get("startPrice") or {}, faixa.get("endPrice") or {}
    if ini.get("units"):
        moeda = _MOEDA.get(ini.get("currencyCode", ""), ini.get("currencyCode", ""))
        return f'{moeda} {ini["units"]}–{fim["units"]}' if fim.get("units") else f'{moeda} {ini["units"]}+'
    return _NIVEL_PRECO.get(lugar.get("priceLevel", ""))


def _horarios(lugar: dict) -> dict | None:
    """["segunda-feira: 11:00–15:00, 18:00–23:00", ...] -> {"segunda-feira": ["11:00–15:00", ...]}."""
    dias = (lugar.get("regularOpeningHours") or {}).get("weekdayDescriptions") or []
    saida = {}
    for d in dias:
        dia, _, faixas = d.partition(": ")
        if dia:
            saida[dia] = [f.strip() for f in faixas.split(",") if f.strip()]
    return saida or None


def _texto(v) -> str | None:
    return (v or {}).get("text") or None


def place_para_lugar(lugar: dict, input_id: str) -> dict:
    """Converte um lugar da Places API (New) no mesmo formato de `linha_para_lugar`."""
    fotos = [f for f in lugar.get("photos") or [] if isinstance(f, dict) and f.get("name")][:MAX_FOTOS]
    urls = [url_foto(f["name"]) for f in fotos]
    local = lugar.get("location") or {}
    return {
        "input_id": input_id,
        "nome": _texto(lugar.get("displayName")) or "",
        "categoria_google": _texto(lugar.get("primaryTypeDisplayName")),
        "endereco": lugar.get("formattedAddress") or None,
        "site": lugar.get("websiteUri") or None,
        "telefone": lugar.get("nationalPhoneNumber") or None,
        "nota": lugar.get("rating"),
        "avaliacoes": lugar.get("userRatingCount"),
        "lat": local.get("latitude"),
        "lon": local.get("longitude"),
        "foto": urls[0] if urls else None,
        "fotos": urls,
        "descricao": None,  # editorialSummary é Atmosphere: mais caro, ficou de fora
        "sobre": [],        # idem (allowsDogs, dineIn…)
        "faixa_preco": _faixa_preco(lugar),
        "horarios": _horarios(lugar),
        "status": _STATUS.get(lugar.get("businessStatus", "")),
        "link_maps": lugar.get("googleMapsUri") or None,
        "place_id": lugar.get("id") or None,
        # Termos do Google: mostrar o autor (nome, avatar e link) junto de cada foto, mais um
        # link para a foto no Google Maps. Mesma ordem de "fotos".
        "fotos_autores": [[{"nome": a.get("displayName"), "uri": a.get("uri"), "avatar": a.get("photoUri"),
                            "link_foto": f.get("googleMapsUri")}
                           for a in f.get("authorAttributions") or [] if isinstance(a, dict)]
                          for f in fotos],
    }


async def _text_search(client: httpx.AsyncClient, texto: str) -> list[dict]:
    r = await client.post(f"{PLACES_URL}/places:searchText",
                          json={"textQuery": texto, "languageCode": "pt-BR", "regionCode": "BR",
                                "pageSize": 20},
                          headers={"X-Goog-Api-Key": _chave_places(), "X-Goog-FieldMask": CAMPOS_PLACES},
                          timeout=TIMEOUT_PLACES_S)
    r.raise_for_status()
    return r.json().get("places") or []


async def _buscar_lote_places(client: httpx.AsyncClient, consultas: dict[str, str]) -> dict[str, list[dict]]:
    if not _chave_places():
        raise GoogleIndisponivel("PV_GOOGLE_FONTE=places, mas PV_GOOGLE_PLACES_KEY está vazia")
    limite = asyncio.Semaphore(BUSCAS_SIMULTANEAS)

    async def uma(cid: str, texto: str) -> tuple[str, list[dict] | None, str]:
        async with limite:
            try:
                brutos = await _text_search(client, texto)
            except (httpx.HTTPError, ValueError) as e:
                log.warning("Places API falhou em %r: %s", texto, e)
                return cid, None, str(e)
        lugares = [place_para_lugar(x, cid) for x in brutos if isinstance(x, dict)]
        return cid, [x for x in lugares if x["nome"]], ""

    resultados = await asyncio.gather(*(uma(cid, t) for cid, t in consultas.items()))
    saida = {cid: lugares for cid, lugares, _ in resultados if lugares is not None}
    if not saida:
        raise GoogleIndisponivel(f"Places API não respondeu: {resultados[0][2]}")
    return saida


# ---------------------------------------------------------------- gosom (protótipo)

def _num(v: str, tipo=float):
    try:
        return tipo(float(v)) if v not in ("", None) else None
    except ValueError:
        return None


def _json(v: str):
    try:
        return json.loads(v) if v else None
    except json.JSONDecodeError:
        return None


def sobre_de_about(valor: str, limite: int = 8) -> list[str]:
    """Opções ativas do campo "about" do gosom: "Aceita pets", "Entrada acessível"…"""
    secoes = _json(valor)
    if not isinstance(secoes, list):
        return []
    nomes = [op["name"] for s in secoes if isinstance(s, dict)
             for op in s.get("options") or [] if isinstance(op, dict) and op.get("enabled") and op.get("name")]
    return nomes[:limite]


def linha_para_lugar(linha: dict) -> dict:
    """Converte uma linha do CSV do gosom no formato usado pelos cards."""
    imagens = [i.get("image") for i in (_json(linha.get("images", "")) or []) if isinstance(i, dict) and i.get("image")]
    return {
        "input_id": linha.get("input_id", ""),
        "nome": linha.get("title", ""),
        "categoria_google": linha.get("category") or None,
        "endereco": linha.get("address") or None,
        "site": linha.get("website") or None,
        "telefone": linha.get("phone") or None,
        "nota": _num(linha.get("review_rating", "")),
        "avaliacoes": _num(linha.get("review_count", ""), int),
        "lat": _num(linha.get("latitude", "")),
        "lon": _num(linha.get("longitude", "")),
        "foto": linha.get("thumbnail") or (imagens[0] if imagens else None),
        "fotos": imagens[:MAX_FOTOS],
        "descricao": linha.get("descriptions") or None,
        "sobre": sobre_de_about(linha.get("about", "")),
        "faixa_preco": linha.get("price_range") or None,
        "horarios": _json(linha.get("open_hours", "")),
        "status": linha.get("status") or None,
        "link_maps": linha.get("link") or None,
        "place_id": linha.get("place_id") or None,
        "fotos_autores": [],  # o gosom não traz o autor das fotos
    }


async def _buscar_lote_gosom(client: httpx.AsyncClient, consultas: dict[str, str], *, lang: str,
                             depth: int, max_time_s: int, intervalo_s: int,
                             espera_max_s: int) -> dict[str, list[dict]]:
    corpo = {
        "name": f"planejador-{uuid.uuid4().hex[:8]}",
        "keywords": [f"{texto} #!#{cid}" for cid, texto in consultas.items()],
        "lang": lang,
        "depth": depth,
        "max_time": max_time_s,  # o gosom recebe em segundos
        "zoom": 14,
    }
    try:
        r = await client.post(f"{GOSOM_URL}/api/v1/jobs", json=corpo, timeout=30)
    except httpx.ConnectError as e:
        raise GoogleIndisponivel(
            f"Não consegui falar com o gosom em {GOSOM_URL}. Ele está rodando no Docker?") from e
    r.raise_for_status()
    job_id = r.json()["id"]

    gasto = 0
    while True:
        await asyncio.sleep(intervalo_s)
        gasto += intervalo_s
        st = (await client.get(f"{GOSOM_URL}/api/v1/jobs/{job_id}", timeout=30)).json()
        status = (st.get("Status") or st.get("status") or "").lower()
        if status == "ok":
            break
        if status == "failed":
            raise RuntimeError(f"Job {job_id} do gosom falhou")
        if gasto >= espera_max_s:
            raise TimeoutError(f"Job {job_id} do gosom passou de {espera_max_s}s")

    csv_txt = (await client.get(f"{GOSOM_URL}/api/v1/jobs/{job_id}/download", timeout=120)).text
    saida: dict[str, list[dict]] = {cid: [] for cid in consultas}
    for linha in csv.DictReader(io.StringIO(csv_txt)):
        lugar = linha_para_lugar(linha)
        if lugar["input_id"] in saida and lugar["nome"]:
            saida[lugar["input_id"]].append(lugar)
    return saida
