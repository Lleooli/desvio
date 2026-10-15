"""Cliente do gosom/google-maps-scraper (open source, MIT) rodando em Docker.

Em vez de manter um raspador próprio (que quebra toda vez que o Google muda o
HTML), usamos o projeto mais maduro do GitHub e conversamos com a API REST dele:

    docker run -p 8080:8080 -v "$PWD/gmapsdata:/gmapsdata" \
        gosom/google-maps-scraper -data-folder /gmapsdata

Todas as buscas da viagem vão num job só. Cada busca leva um ID próprio
(sintaxe "consulta #!#id" do gosom), e assim cada resultado volta marcado com
a parada e a categoria a que pertence.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import uuid

import httpx

GOSOM_URL = os.getenv("PV_GOSOM_URL", "http://localhost:8080")


class GosomIndisponivel(RuntimeError):
    pass


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
        "fotos": imagens[:6],
        "descricao": linha.get("descriptions") or None,
        "faixa_preco": linha.get("price_range") or None,
        "horarios": _json(linha.get("open_hours", "")),
        "status": linha.get("status") or None,
        "link_maps": linha.get("link") or None,
        "place_id": linha.get("place_id") or None,
    }


async def buscar_lote(client: httpx.AsyncClient, consultas: dict[str, str], *, lang: str = "pt",
                      depth: int = 1, max_time_s: int = 600, intervalo_s: int = 10,
                      espera_max_s: int = 1800) -> dict[str, list[dict]]:
    """Envia {id: "restaurantes em Lages, SC", ...} num job e devolve {id: [lugares]}."""
    if not consultas:
        return {}
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
        raise GosomIndisponivel(
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
