"""Encontra o Instagram de um restaurante sem raspar o Instagram.

Ordem de tentativa:
1. O "site" cadastrado já é o Instagram (muito comum em restaurantes do Brasil)
2. O site do lugar tem um link para o Instagram (rodapé, ícones)
3. Busca web gratuita com a biblioteca ddgs (deedy5/ddgs, MIT), que agrega
   Google, Bing, DuckDuckGo etc. sem chave de API

O resultado do passo 3 vem marcado como "busca", porque pode errar quando há
restaurantes com nome parecido. Vale mostrar no card como "provável".

O resultado fica no cache por id do lugar (30 dias, #93): a mesma viagem feita de
novo não refaz as buscas, que eram a maior parte do tempo de uma viagem já em cache.
"Sem Instagram" vale só 7 dias, como o "gmaps-vazio" do Google: o lugar pode criar um.
"""
from __future__ import annotations

import asyncio
import difflib
import re
import unicodedata

import httpx

from . import cache

# "não achamos Instagram" vale menos que um achado: o lugar pode criar um perfil
VAZIO_DIAS = 7
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


def _palavras(nome: str) -> list[str]:
    return [p for p in _norm(nome).split() if len(p) > 3 and p not in {"restaurante", "pizzaria", "lanchonete", "cafe", "churrascaria", "bar"}]


def parece_o_mesmo(nome: str, texto: str, todas: bool = False) -> bool:
    """Uma palavra significativa do nome (ou todas, com todas=True) aparece no resultado."""
    alvo = _norm(texto).replace(" ", "")
    palavras = _palavras(nome)
    if not palavras:
        return _norm(nome).replace(" ", "") in alvo
    return (all if todas else any)(p in alvo for p in palavras)


def escolher_handle(nome: str, cidade: str, resultados: list[dict]) -> str | None:
    """Melhor perfil entre os resultados da busca: nome parecido e, de preferência, da cidade."""
    alvo = _norm(nome).replace(" ", "")
    cid = _norm(cidade).replace(" ", "")
    melhor, melhor_nota = None, 0.0
    for res in resultados:
        h = handle_de_texto(res.get("href", ""))
        texto = f'{res.get("title", "")} {res.get("body", "")}'
        if not h or not parece_o_mesmo(nome, f"{texto} {h}", todas=True):
            continue
        nota = difflib.SequenceMatcher(None, alvo, _norm(h).replace(" ", "")).ratio()
        if cid and cid in _norm(texto).replace(" ", ""):
            nota += 1.0
        if nota > melhor_nota:
            melhor, melhor_nota = h, nota
    return melhor if melhor_nota >= 0.5 else None


def handles_de_texto(texto: str) -> list[str]:
    """Todos os perfis citados no texto, na ordem, sem repetir."""
    vistos: list[str] = []
    for m in IG.finditer(texto or ""):
        h = m.group(1).rstrip(".")
        if h.lower() not in NAO_PERFIL and h.lower() not in (v.lower() for v in vistos):
            vistos.append(h)
    return vistos


def _dominio(url: str) -> str:
    """"http://www.churrascariaprodocimo.com.br/" -> "churrascariaprodocimo"."""
    host = re.sub(r"^[a-z]+://", "", (url or "").lower()).split("/")[0].split(":")[0]
    partes = [p for p in host.split(".") if p not in {"www", "com", "br", "net", "org", "site", "wixsite"}]
    return partes[0] if partes else ""


def combina_com_o_lugar(handle: str, nome: str, site: str = "") -> bool:
    """Se o perfil parece ser do próprio lugar, pelo nome ou pelo domínio do site.

    O site de um restaurante costuma ter no rodapé o Instagram de quem fez o site
    ("desenvolvido por @agencia"); esse perfil não tem nada do nome nem do domínio.
    """
    h = _norm(handle).replace(" ", "")
    if parece_o_mesmo(nome, h):
        return True
    alvo = _norm(nome).replace(" ", "")
    if alvo and difflib.SequenceMatcher(None, alvo, h).ratio() >= 0.6:
        return True
    dominio = _norm(_dominio(site)).replace(" ", "")
    return len(dominio) >= 4 and (dominio in h or h in dominio
                                  or difflib.SequenceMatcher(None, dominio, h).ratio() >= 0.6)


async def do_site(client: httpx.AsyncClient, url: str, nome: str = "") -> str | None:
    """O perfil do lugar citado no site; perfil que não combina com o lugar é descartado."""
    candidatos = handles_de_texto(url)
    if not candidatos:
        try:
            r = await client.get(url, headers=NAVEGADOR, timeout=12, follow_redirects=True)
            candidatos = handles_de_texto(r.text[:500_000])
        except (httpx.HTTPError, ValueError):
            return None
    if not nome:
        return candidatos[0] if candidatos else None
    return next((h for h in candidatos if combina_com_o_lugar(h, nome, url)), None)


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
    return escolher_handle(nome, cidade, resultados or [])


async def completar(client: httpx.AsyncClient, cards: list[dict], usar_busca: bool = True,
                    categorias: tuple[str, ...] = ("restaurante",)) -> None:
    """Preenche card["instagram"] in-place, lendo e gravando o cache por id do lugar."""
    for c in cards:
        if c.get("categoria") not in categorias or c.get("instagram"):
            continue
        lugar = c.get("id")
        if lugar:
            guardado = cache.obter("instagram2|" + lugar)
            if guardado is None:
                guardado = cache.obter("instagram2-vazio|" + lugar, dias=VAZIO_DIAS)
            if isinstance(guardado, dict):
                if guardado.get("handle"):
                    c["instagram"] = f'https://instagram.com/{guardado["handle"]}'
                    c["instagram_origem"] = guardado.get("origem")
                continue
        h, origem = None, None
        if c.get("site"):
            h, origem = await do_site(client, c["site"], c.get("nome") or ""), "site"
        if not h and usar_busca:
            h, origem = await por_busca(c["nome"], c.get("cidade", "")), "busca"
            await asyncio.sleep(1.5)  # gentileza com os buscadores
        if h:
            c["instagram"] = f"https://instagram.com/{h}"
            c["instagram_origem"] = origem
            if lugar:
                cache.guardar("instagram2|" + lugar, {"handle": h, "origem": origem})
        elif lugar and usar_busca:  # sem a busca, "não achou" ainda não é resposta
            cache.guardar("instagram2-vazio|" + lugar, {})
