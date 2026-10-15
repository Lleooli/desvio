"""Encontra o Instagram de um restaurante sem raspar o Instagram.

Ordem de tentativa:
1. O "site" cadastrado já é o Instagram (muito comum em restaurantes do Brasil)
2. O site do lugar tem um link para o Instagram (rodapé, ícones)
3. Busca web gratuita com a biblioteca ddgs (deedy5/ddgs, MIT), que agrega
   Google, Bing, DuckDuckGo etc. sem chave de API

O resultado do passo 3 vem marcado como "busca", porque pode errar quando há
restaurantes com nome parecido. Vale mostrar no card como "provável".
"""
from __future__ import annotations

import asyncio
import re
import unicodedata

import httpx

IG = re.compile(r"instagram\.com/([A-Za-z0-9_.]{2,30})", re.I)
NAO_PERFIL = {"p", "reel", "reels", "explore", "stories", "accounts", "tv", "share",
              "instagram", "about", "legal", "developer", "direct", "web"}
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"}


def handle_de_texto(texto: str) -> str | None:
    for m in IG.finditer(texto or ""):
        h = m.group(1).rstrip(".")
        if h.lower() not in NAO_PERFIL:
            return h
    return None


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", " ", s)


def parece_o_mesmo(nome: str, texto: str) -> bool:
    """Pelo menos uma palavra significativa do nome aparece no resultado."""
    alvo = _norm(texto).replace(" ", "")
    palavras = [p for p in _norm(nome).split() if len(p) > 3 and p not in {"restaurante", "pizzaria", "lanchonete", "cafe", "churrascaria", "bar"}]
    return any(p in alvo for p in palavras) if palavras else _norm(nome).replace(" ", "") in alvo


async def do_site(client: httpx.AsyncClient, url: str) -> str | None:
    if handle_de_texto(url):
        return handle_de_texto(url)
    try:
        r = await client.get(url, headers=NAVEGADOR, timeout=12, follow_redirects=True)
        return handle_de_texto(r.text[:500_000])
    except (httpx.HTTPError, ValueError):
        return None


async def por_busca(nome: str, cidade: str) -> str | None:
    try:
        from ddgs import DDGS
    except ImportError:
        return None

    def _buscar():
        return DDGS().text(f"{nome} {cidade} instagram", region="br-pt", max_results=6)

    try:
        resultados = await asyncio.to_thread(_buscar)
    except Exception:  # bloqueio temporário, sem rede etc.
        return None
    for r in resultados or []:
        texto = f'{r.get("href", "")} {r.get("title", "")}'
        h = handle_de_texto(r.get("href", ""))
        if h and parece_o_mesmo(nome, texto + " " + h):
            return h
    return None


async def completar(client: httpx.AsyncClient, cards: list[dict], usar_busca: bool = True,
                    categorias: tuple[str, ...] = ("restaurante",)) -> None:
    """Preenche card["instagram"] in-place."""
    for c in cards:
        if c.get("categoria") not in categorias or c.get("instagram"):
            continue
        h, origem = None, None
        if c.get("site"):
            h, origem = await do_site(client, c["site"]), "site"
        if not h and usar_busca:
            h, origem = await por_busca(c["nome"], c.get("cidade", "")), "busca"
            await asyncio.sleep(1.5)  # gentileza com os buscadores
        if h:
            c["instagram"] = f"https://instagram.com/{h}"
            c["instagram_origem"] = origem
