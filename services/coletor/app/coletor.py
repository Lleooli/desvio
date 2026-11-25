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

from . import cache, fronteira, geo, gmaps, instagram, osm

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
# busca do Google que voltou vazia (cidade sem nada ou que o gosom não alcançou) vale só 1 dia
VAZIO_GOOGLE_DIAS = 1


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


def _escolher(i: int, p: dict, brutos: list[dict], google: dict[str, list[dict]], categorias: list[str],
              por_categoria: int, nota_minima: float) -> list[dict]:
    """Cards de uma parada: Google primeiro (pela nota), completados com OSM, sem lugar repetido.

    O mesmo lugar pode voltar do Google em duas categorias (um parque em "turismo" e em
    "natureza"): fica só na primeira, por id e por nome.
    """
    centro = (p["lat"], p["lon"])
    cards: list[dict] = []
    vistos: set[str] = set()
    ids: set[str] = set()
    for cat in categorias:
        escolhidos: list[dict] = []
        candidatos = [g for g in google.get(f"{i}|{cat}", [])
                      if g["lat"] is not None
                      and geo.distancia_km(centro, (g["lat"], g["lon"])) <= p["raio_km"] * 2
                      and (g["nota"] is None or g["nota"] >= nota_minima)
                      and (g.get("status") or "").lower() not in {"closed permanently", "fechado permanentemente"}]
        # nota bayesiana: 4,8 com 5 avaliações não passa na frente de 4,6 com 2.000
        candidatos.sort(key=lambda g: -((g["nota"] or 0) * (g["avaliacoes"] or 0) + 4.2 * 30) / ((g["avaliacoes"] or 0) + 30))
        for g in candidatos:
            if len(escolhidos) >= por_categoria:
                break
            card = _card_google(g, cat, p)
            if card["id"] in ids or _norm(g["nome"]) in vistos:
                continue
            escolhidos.append(card)
            ids.add(card["id"])
            vistos.add(_norm(g["nome"]))
        osm_cat = sorted((x for x in brutos if x["categoria"] == cat), key=lambda x: -osm.relevancia(x, centro))
        for x in osm_cat:
            if len(escolhidos) >= por_categoria:
                break
            if _norm(x["nome"]) not in vistos:
                escolhidos.append(_card_osm(x, p))
                vistos.add(_norm(x["nome"]))
        cards.extend(escolhidos)
    return cards


def _manter_enviados(finais: list[dict], enviados: list[dict]) -> list[dict]:
    """Junta o resultado final com o parcial sem repetir lugar.

    O app já mostrou os cards do parcial: eles continuam, com o mesmo id. Se o Google
    trouxe o mesmo lugar (mesmo nome), os dados do Google entram no card que já existia.
    Assim o final contém todos os ids do parcial e nenhum lugar aparece duas vezes.
    """
    por_nome = {_norm(c["nome"]): c for c in enviados}
    saida, usados = [], set()
    for c in finais:
        antigo = por_nome.get(_norm(c["nome"]))
        if antigo is None:
            saida.append(c)
        elif id(antigo) not in usados:
            if c["id"] != antigo["id"]:  # Google achou o mesmo lugar: enriquece, mantém o id
                antigo.update({k: v for k, v in c.items() if k not in ("id", "fonte") and v not in (None, "", [])})
                antigo["fonte"] = "openstreetmap+google_maps"
            saida.append(antigo)
            usados.add(id(antigo))
    return saida + [c for c in enviados if id(c) not in usados]


async def _completar_wikipedia(client: httpx.AsyncClient, cards: list[dict]) -> None:
    """Foto e resumo da Wikipedia para atrações do OSM sem foto (uma tentativa por card)."""
    sem_foto = [c for c in cards if not c.get("foto") and c.get("wikipedia") and not c.get("_wiki_tentada")]
    for c, (foto, resumo) in zip(sem_foto, await asyncio.gather(
            *(osm.resumo_wikipedia(client, c["wikipedia"]) for c in sem_foto))):
        c["foto"] = c["foto"] or foto
        c["descricao"] = c.get("descricao") or resumo
    for c in sem_foto:
        c["_wiki_tentada"] = True


async def _cidade_proxima_com_cache(client: httpx.AsyncClient, ponto: tuple[float, float]) -> dict | None:
    chave = f"cidade_proxima|{ponto[0]:.3f}|{ponto[1]:.3f}"
    guardado = cache.obter(chave)
    if guardado is not None:
        return guardado["cidade"]
    cidade = await osm.cidade_proxima(client, ponto)
    cache.guardar(chave, {"cidade": cidade})
    return cidade


async def _pois_com_cache(client: httpx.AsyncClient, p: dict, categorias: list[str]) -> list[dict]:
    """Lugares do OSM da parada; só pergunta ao Overpass as categorias que o cache não tem."""
    chaves = {cat: f'osm|{_norm(p["nome"])}|{p.get("uf") or ""}|{p["raio_km"]:g}|{cat}' for cat in categorias}
    por_cat = {cat: cache.obter(ch) for cat, ch in chaves.items()}
    faltam = [cat for cat, v in por_cat.items() if v is None]
    if faltam:
        novos = await osm.pois(client, (p["lat"], p["lon"]), p["raio_km"], faltam)
        for cat in faltam:
            por_cat[cat] = [x for x in novos if x["categoria"] == cat]
            cache.guardar(chaves[cat], por_cat[cat])
    return [x for cat in categorias for x in por_cat[cat]]


async def montar_cards(client: httpx.AsyncClient, paradas: list[dict], categorias: list[str],
                       por_categoria: int, usar_google_maps: bool, buscar_instagram: bool,
                       nota_minima: float = 4.0, progresso: Progresso | None = None,
                       ao_ter_parcial: Callable[[list[dict]], None] | None = None) -> list[dict]:
    """Recebe paradas {nome, uf, lat, lon, raio_km} e devolve as mesmas com "cards".

    Com o Google ligado, `ao_ter_parcial` recebe antes as paradas só com cards do OSM.
    """
    # O que o cache (30 dias, entre usuários) já tem do Google não vai para o Google de novo
    google: dict[str, list[dict]] = {}
    faltam_google: dict[str, str] = {}
    if usar_google_maps:
        for i, p in enumerate(paradas):
            for cat in categorias:
                if cat not in CONSULTA_GOOGLE:
                    continue
                texto = _consulta_cidade(cat, p)
                guardado = cache.obter("gmaps|" + texto)
                if guardado is None:
                    guardado = cache.obter("gmaps-vazio|" + texto, dias=VAZIO_GOOGLE_DIAS)
                if guardado is None:
                    faltam_google[f"{i}|{cat}"] = texto
                else:
                    google[f"{i}|{cat}"] = guardado

    # 1) Base gratuita e estável: OpenStreetMap (com cache por cidade, UF e categoria)
    lento = bool(faltam_google) and gmaps.fonte() == "gosom"  # a Places API responde em segundos
    leva = "leva uns 3 minutos" if lento else "leva menos de 1 minuto"
    brutos = []
    for i, p in enumerate(paradas):
        _avisar(progresso, "lugares", "Buscando fotos e notas", f'{p["nome"]} agora · {leva}',
                35 + 40 * i // len(paradas))
        brutos.append(await _pois_com_cache(client, p, categorias))

    # 2) Google Maps (gmaps.py: Places API ou gosom). No gosom é um job só para a viagem
    #    inteira e leva minutos, então antes entrega um parcial só com OpenStreetMap,
    #    para a pessoa já ir deslizando.
    avisos: list[str] = []
    enviados: list[list[dict]] = []  # cards do parcial, por parada
    if faltam_google:
        if ao_ter_parcial:
            enviados = [_escolher(i, p, brutos[i], {}, categorias, por_categoria, nota_minima)
                        for i, p in enumerate(paradas)]
            await _completar_wikipedia(client, [c for cs in enviados for c in cs])
            ao_ter_parcial([{**p, "cards": [{k: v for k, v in c.items() if not k.startswith("_")} for c in cs]}
                            for p, cs in zip(paradas, enviados)])
        _avisar(progresso, "lugares", "Buscando fotos e notas", f"Google Maps · {leva}", 75)
        try:
            novos = await gmaps.buscar_lote(client, faltam_google)
            # os termos da Places API proíbem guardar o conteúdo dos lugares (só o place_id):
            # com a API oficial, nada do Google vai para o cache compartilhado
            guardar_google = gmaps.fonte() != "places"
            for cid, lugares in novos.items() if guardar_google else ():
                # vazio pode ser cidade que o gosom não alcançou antes do max_time: em vez de
                # 30 dias de "nada", vale só 1 dia (chave à parte, lida com dias=1)
                chave = "gmaps|" if lugares else "gmaps-vazio|"
                cache.guardar(chave + faltam_google[cid], lugares)
            google.update(novos)
        except (gmaps.GosomIndisponivel, RuntimeError, TimeoutError, httpx.HTTPError) as e:
            log.warning("Google Maps indisponível; seguindo só com OpenStreetMap: %s", e)
            avisos.append("O Google Maps não respondeu, então os lugares vieram só do OpenStreetMap.")

    # 3) Junta, prioriza e corta por categoria; o que já foi no parcial continua, com o mesmo id
    for i, p in enumerate(paradas):
        cards = _escolher(i, p, brutos[i], google, categorias, por_categoria, nota_minima)
        p["cards"] = _manter_enviados(cards, enviados[i]) if enviados else cards

    todos = [c for p in paradas for c in p["cards"]]

    # 4) Fotos e resumos da Wikipedia para atrações do OSM sem foto
    await _completar_wikipedia(client, todos)

    # 5) Instagram dos restaurantes
    restaurantes = sum(1 for c in todos if c.get("categoria") == "restaurante")
    _avisar(progresso, "instagram", "Instagram dos restaurantes",
            f"{restaurantes} restaurante{'s' if restaurantes != 1 else ''}", 90)
    await instagram.completar(client, todos, usar_busca=buscar_instagram)
    for c in todos:
        c.pop("_wiki_tentada", None)

    if avisos:
        for p in paradas:
            p.setdefault("avisos", []).extend(avisos)
    return paradas


async def planejar_viagem(origem: str, destino: str, intervalo_km: float = 200,
                          categorias: list[str] | None = None, por_categoria: int = 5,
                          usar_google_maps: bool = False, buscar_instagram: bool = True,
                          veiculo: str = "carro",
                          raio_parada_km: float = 8, raio_destino_km: float = 15,
                          progresso: Progresso | None = None,
                          parcial: Callable[[dict], None] | None = None) -> dict:
    """Viagem por terra (carro, moto ou bicicleta) com paradas a cada `intervalo_km`.

    `progresso` recebe as etapas na ordem: rota, cidades, lugares, instagram.
    `parcial` recebe, com o Google ligado, o resultado só com OpenStreetMap antes do
    gosom (minutos); o resultado final contém todos os cards do parcial, com os mesmos ids.
    """
    categorias = categorias or CATEGORIAS_PADRAO
    async with httpx.AsyncClient() as client, cache.sessao():  # uma conexão com o cache por job
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
        # viagem entre duas cidades do Brasil não para em outro país (issue #95), nem quando a
        # rota encosta na fronteira e a cidade maior perto da estrada é Ciudad del Este
        so_brasil = fronteira.no_brasil((o["lat"], o["lon"])) and fronteira.no_brasil((d["lat"], d["lon"]))
        if rota.get("sai_do_brasil"):
            log.warning("rota de %s a %s sai do Brasil; as paradas de fora ficam de fora", origem, destino)
        for km, ponto in geo.amostrar(pontos, intervalo_km):
            if total - km < intervalo_km * 0.5:
                break  # muito perto do destino, que já entra separado
            cidade = await _cidade_proxima_com_cache(client, ponto)
            if not cidade or _norm(cidade["nome"]) in vistas:
                continue
            vistas.add(_norm(cidade["nome"]))
            if so_brasil and not fronteira.no_brasil((cidade["lat"], cidade["lon"])):
                continue  # longe da fronteira: nem pergunta ao Nominatim
            _, uf, pais = await geo.cidade_uf_pais(client, (cidade["lat"], cidade["lon"]))
            if so_brasil and pais not in (None, "br"):
                continue
            paradas.append({**cidade, "uf": uf, "tipo": "parada", "raio_km": raio_parada_km})
        paradas.append({"nome": d["nome"], "uf": d["uf"], "lat": d["lat"], "lon": d["lon"],
                        "tipo": "destino", "raio_km": raio_destino_km})
        _avisar(progresso, "cidades", *texto_cidades(len(paradas) - 1, intervalo_km), 35)

        def resultado(com_cards: list[dict]) -> dict:
            for p in com_cards:
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
                "paradas": com_cards,
            }

        def ao_ter_parcial(com_cards: list[dict]) -> None:
            if not parcial:
                return
            try:
                parcial(resultado(com_cards))
            except Exception:  # gravar o parcial nunca derruba a coleta
                log.warning("não consegui gravar o resultado parcial", exc_info=True)

        await montar_cards(client, paradas, categorias, por_categoria, usar_google_maps, buscar_instagram,
                           progresso=progresso, ao_ter_parcial=ao_ter_parcial)

    return resultado(paradas)
