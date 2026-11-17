"""Testes sem internet: as APIs externas são simuladas com httpx.MockTransport."""
import asyncio
import csv
import io
import json
from urllib.parse import parse_qs

import httpx
import pytest

from app import coletor, geo, gmaps, instagram, osm, preferencias, roteiro

# Rota reta simulada: de (-29.78,-55.79) subindo ~1.000 km para o norte
ROTA = [(-29.78 + i * 0.09, -55.79 + i * 0.02) for i in range(101)]


def test_amostrar_e_km():
    acc = geo.acumuladas(ROTA)
    pts = geo.amostrar(ROTA, 200)
    assert len(pts) == int(acc[-1] // 200)
    assert all(abs(geo.km_na_rota(ROTA, acc, p) - km) < 12 for km, p in pts)


def test_instagram_regex():
    assert instagram.handle_de_texto("https://www.instagram.com/pizzaria_x/") == "pizzaria_x"
    assert instagram.handle_de_texto("https://instagram.com/p/abc123") is None
    assert instagram.parece_o_mesmo("Churrascaria Gaúcha Lages", "churrascariagauchalages | Instagram")
    assert not instagram.parece_o_mesmo("Restaurante Bom Sabor", "outro lugar qualquer")


def test_osm_categoria_e_tags():
    assert osm.categoria({"amenity": "fuel"}) == "posto"
    assert osm.categoria({"tourism": "viewpoint"}) == "turismo"
    assert osm.categoria({"natural": "waterfall"}) == "natureza"
    assert osm.instagram_das_tags({"contact:instagram": "@meu.bar"}) == "https://instagram.com/meu.bar"
    assert "Special:FilePath" in osm.foto_das_tags({"wikimedia_commons": "File:Foto 1.jpg"})


def test_roteiro_ordena_pelo_km_na_rota():
    assert roteiro.ordenar_na_rota([{"km_na_rota": 5}, {"km_na_rota": 1}])[0]["km_na_rota"] == 1
    assert roteiro.ordenar_na_rota([{"km_na_rota": None}, {}])  # sem km não quebra


def test_preferencias(pessoa):
    leo, _ = pessoa
    for i, (cat, ok) in enumerate([("restaurante", 1), ("restaurante", 1), ("posto", 0), ("posto", 0)]):
        preferencias.registrar(leo, {"id": f"c{i}", "categoria": cat, "nota": 4.5}, bool(ok))
    p = preferencias.perfil(leo)
    assert p["categoria"]["restaurante"]["taxa"] == 1.0 and p["categoria"]["posto"]["taxa"] == 0.0
    ordem = preferencias.pontuar([{"id": "a", "categoria": "posto"}, {"id": "b", "categoria": "restaurante"}], p)
    assert ordem[0]["id"] == "b"
    assert preferencias.ja_vistos(leo) == {"c0", "c1", "c2", "c3"}
    preferencias.registrar(leo, {"id": "c2", "categoria": "posto"}, True)  # mudou de ideia: troca, não duplica
    assert preferencias.perfil(leo)["total_swipes"] == 4


# ---------- fluxo completo com serviços simulados ----------

def _csv_gosom(linhas):
    cab = ["input_id", "link", "title", "category", "address", "open_hours", "website", "phone",
           "review_count", "review_rating", "latitude", "longitude", "status", "descriptions",
           "thumbnail", "price_range", "place_id", "images"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cab)
    w.writeheader()
    for l in linhas:
        w.writerow({k: l.get(k, "") for k in cab})
    return buf.getvalue()


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "nominatim" in url and "/search" in url:
        q = request.url.params["q"]
        lat, lon = (ROTA[0] if "Alegrete" in q else ROTA[-1])
        nome = "Alegrete" if "Alegrete" in q else "Destino"
        return httpx.Response(200, json=[{"lat": str(lat), "lon": str(lon), "display_name": q,
                                          "address": {"city": nome, "ISO3166-2-lvl4": "BR-RS"}}])
    if "nominatim" in url and "/reverse" in url:
        return httpx.Response(200, json={"address": {"city": "X", "ISO3166-2-lvl4": "BR-SC"}})
    if "router.project-osrm.org" in url or "routed-bike" in url:
        _handler.rotas = getattr(_handler, "rotas", []) + [url]
        duracao = 240_000 if "routed-bike" in url else 50_000  # bike: ~15 km/h
        return httpx.Response(200, json={"code": "Ok", "routes": [{"distance": 1_000_000, "duration": duracao,
                              "geometry": {"coordinates": [[lo, la] for la, lo in ROTA]}}]})
    if "overpass" in url:
        corpo = parse_qs(request.content.decode())["data"][0]
        if "place" in corpo:
            lat = float(corpo.split("around:")[1].split(",")[1])
            lon = float(corpo.split("around:")[1].split(",")[2].split(")")[0])
            return httpx.Response(200, json={"elements": [
                {"type": "node", "id": 1, "lat": lat + 0.01, "lon": lon, "tags": {"name": f"Cidade{lat:.1f}", "population": "50000"}}]})
        lat = float(corpo.split("around:")[1].split(",")[1])
        lon = float(corpo.split("around:")[1].split(",")[2].split(")")[0])
        return httpx.Response(200, json={"elements": [
            {"type": "node", "id": 10, "lat": lat, "lon": lon, "tags": {"name": "Posto Sul", "amenity": "fuel"}},
            {"type": "node", "id": 11, "lat": lat, "lon": lon, "tags": {"name": "Mirante", "tourism": "viewpoint", "wikipedia": "pt:Mirante"}},
            {"type": "way", "id": 12, "center": {"lat": lat, "lon": lon}, "tags": {"name": "Cantina Boa", "amenity": "restaurant", "website": "https://cantina.example"}},
        ]})
    if "wikipedia.org" in url:
        return httpx.Response(200, json={"thumbnail": {"source": "https://img/mirante.jpg"}, "extract": "Um mirante."})
    if "cantina.example" in url:
        return httpx.Response(200, text='<a href="https://www.instagram.com/cantinaboa/">IG</a>')
    if url.endswith("/api/v1/jobs") and request.method == "POST":
        corpo = json.loads(request.content)
        _handler.keywords = corpo["keywords"]
        return httpx.Response(201, json={"id": "job1"})
    if url.endswith("/api/v1/jobs/job1"):
        return httpx.Response(200, json={"ID": "job1", "Status": "ok"})
    if url.endswith("/download"):
        linhas = []
        for kw in _handler.keywords:
            texto, cid = [x.strip() for x in kw.split("#!#")]
            i = int(cid.split("|")[0])
            if cid.endswith("restaurante"):
                linhas.append({"input_id": cid, "title": f"Churrascaria {i}", "review_rating": "4.700000",
                               "review_count": "1500.000000", "latitude": str(ROTA[min((i + 1) * 20, 100)][0]),
                               "longitude": str(ROTA[min((i + 1) * 20, 100)][1]), "website": f"https://instagram.com/churras{i}",
                               "thumbnail": "https://lh5/x.jpg", "place_id": f"P{i}",
                               "images": json.dumps([{"title": "a", "image": "https://lh5/1.jpg"}])})
                linhas.append({"input_id": cid, "title": "Ruim", "review_rating": "3.1", "review_count": "10",
                               "latitude": str(ROTA[0][0]), "longitude": str(ROTA[0][1])})
        return httpx.Response(200, text=_csv_gosom(linhas))
    return httpx.Response(404)


@pytest.fixture
def mock_http(monkeypatch):
    original = httpx.AsyncClient

    class Cliente(original):
        def __init__(self, *a, **k):
            k["transport"] = httpx.MockTransport(_handler)
            super().__init__(*a, **k)

    monkeypatch.setattr(httpx, "AsyncClient", Cliente)
    monkeypatch.setattr(coletor.httpx, "AsyncClient", Cliente)

    async def sem_espera(*_):
        return None

    real_sleep = asyncio.sleep
    monkeypatch.setattr(geo.asyncio, "sleep", lambda s: real_sleep(0))
    monkeypatch.setattr(instagram, "por_busca", lambda *a: sem_espera())
    geo._cache.clear()


def test_fluxo_carro_sem_google(mock_http):
    r = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200))
    assert r["rota"]["distancia_km"] == 1000 and r["veiculo"] == "carro"
    nomes = [p["nome"] for p in r["paradas"]]
    assert nomes[-1] == "Destino" and len(nomes) >= 4
    cards = r["paradas"][0]["cards"]
    assert {c["categoria"] for c in cards} == {"turismo", "restaurante", "posto"}
    mirante = next(c for c in cards if c["nome"] == "Mirante")
    assert mirante["foto"] == "https://img/mirante.jpg"
    cantina = next(c for c in cards if c["nome"] == "Cantina Boa")
    assert cantina["instagram"] == "https://instagram.com/cantinaboa" and cantina["instagram_origem"] == "site"
    kms = [p["km_na_rota"] for p in r["paradas"]]
    assert kms == sorted(kms)


def test_fluxo_carro_com_google(mock_http, monkeypatch):
    real_sleep = asyncio.sleep
    monkeypatch.setattr(gmaps.asyncio, "sleep", lambda s: real_sleep(0))
    r = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True))
    assert any("#!#" in k and ", SC #!#" in k for k in _handler.keywords)
    parada = r["paradas"][1]
    rest = [c for c in parada["cards"] if c["categoria"] == "restaurante"]
    assert rest[0]["fonte"] == "google_maps" and rest[0]["nota"] == 4.7 and rest[0]["avaliacoes"] == 1500
    assert rest[0]["instagram"].startswith("https://instagram.com/churras")
    assert all(c["nome"] != "Ruim" for p in r["paradas"] for c in p["cards"])  # nota baixa / longe filtrados
    assert any(c["fonte"] == "openstreetmap" for c in rest)  # completado com OSM


def test_api(mock_http, pessoa):
    from fastapi.testclient import TestClient
    from app import worker
    from app.main import app
    _, cab = pessoa
    cli = TestClient(app, headers=cab)
    r = cli.post("/viagem", json={"origem": "Alegrete, RS", "destino": "Destino, BA", "veiculo": "moto",
                                  "intervalo_km": 300})
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    assert cli.get(f"/jobs/{jid}").json()["status"] == "pendente"
    assert asyncio.run(worker.rodar_uma_vez())
    j = cli.get(f"/jobs/{jid}").json()
    assert j["status"] == "pronto", j
    assert j["resultado"]["veiculo"] == "moto" and j["resultado"]["intervalo_km"] == 300
    cards = j["resultado"]["paradas"][0]["cards"]
    assert cli.post("/swipe", json={"card": cards[0], "gostou": True}).json()["ok"]
    assert cli.get("/perfil").json()["aceitos"] == 1
    r = cli.post("/roteiro", json={"cards": cards[::-1]}).json()
    assert [c["km_na_rota"] for c in r["itens"]] == sorted(c["km_na_rota"] for c in cards)


def test_bicicleta_usa_o_servidor_de_bike(mock_http):
    _handler.rotas = []
    r = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 60, veiculo="bicicleta"))
    assert len(_handler.rotas) == 1 and "routed-bike" in _handler.rotas[0]
    assert r["veiculo"] == "bicicleta" and r["rota"]["duracao_h"] == pytest.approx(66.7, abs=0.1)


def test_moto_usa_a_rota_de_carro(mock_http):
    _handler.rotas = []
    asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, veiculo="moto"))
    assert "router.project-osrm.org" in _handler.rotas[0]


def test_parcial_so_com_osm_chega_antes_do_google_e_final_nao_repete(mock_http, monkeypatch):
    real_sleep = asyncio.sleep
    monkeypatch.setattr(gmaps.asyncio, "sleep", lambda s: real_sleep(0))
    _handler.keywords = None
    parciais = []

    def ao_ter(r):
        parciais.append((r, _handler.keywords))  # keywords só existe depois do POST ao gosom
    final = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True,
                                                parcial=ao_ter))
    assert len(parciais) == 1
    parcial, gosom_ja_chamado = parciais[0]
    assert gosom_ja_chamado is None
    cards_p = [c for p in parcial["paradas"] for c in p["cards"]]
    assert cards_p and all(c["fonte"] == "openstreetmap" for c in cards_p)
    assert all("km_na_rota" in c for c in cards_p) and not any(k.startswith("_") for c in cards_p for k in c)

    for pp, pf in zip(parcial["paradas"], final["paradas"]):
        ids_final = [c["id"] for c in pf["cards"]]
        assert len(ids_final) == len(set(ids_final))                      # nenhum card duas vezes
        assert {c["id"] for c in pp["cards"]} <= set(ids_final)          # o que a pessoa já viu continua
    assert any(c["fonte"] == "google_maps" for p in final["paradas"] for c in p["cards"])
    for p in final["paradas"]:
        nomes = [coletor._norm(c["nome"]) for c in p["cards"]]
        assert len(nomes) == len(set(nomes))
    assert not any(k.startswith("_") for p in final["paradas"] for c in p["cards"] for k in c)


def _contar_chamadas(monkeypatch):
    """Envolve o _handler do mock para contar as chamadas por serviço."""
    cont = {"gosom": 0, "overpass": 0, "nominatim": 0, "osrm": 0}
    original = httpx.MockTransport.handle_async_request

    async def contando(self, request):
        url = str(request.url)
        if url.endswith("/api/v1/jobs") and request.method == "POST":
            cont["gosom"] += 1
        elif "overpass" in url:
            cont["overpass"] += 1
        elif "nominatim" in url:
            cont["nominatim"] += 1
        elif "route/v1" in url:
            cont["osrm"] += 1
        return await original(self, request)
    monkeypatch.setattr(httpx.MockTransport, "handle_async_request", contando)
    return cont


def test_segunda_viagem_pela_mesma_rota_nao_chama_gosom_nem_osm(mock_http, monkeypatch, pg):
    import time
    real_sleep = asyncio.sleep
    monkeypatch.setattr(gmaps.asyncio, "sleep", lambda s: real_sleep(0))
    cont = _contar_chamadas(monkeypatch)
    primeira = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True))
    assert cont["gosom"] == 1 and cont["overpass"] > 0 and cont["osrm"] == 1

    geo._cache.clear()  # outro processo do worker: só o cache no Postgres sobrevive
    for k in cont:
        cont[k] = 0
    parciais = []
    inicio = time.perf_counter()
    segunda = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True,
                                                  parcial=parciais.append))
    gasto = time.perf_counter() - inicio
    assert cont == {"gosom": 0, "overpass": 0, "nominatim": 0, "osrm": 0}
    assert parciais == []  # tudo do cache: nem precisa de parcial
    assert [c["id"] for p in segunda["paradas"] for c in p["cards"]] == \
           [c["id"] for p in primeira["paradas"] for c in p["cards"]]
    assert gasto < 5


def test_lugares_com_mais_de_30_dias_sao_coletados_de_novo(mock_http, monkeypatch, pg):
    import psycopg
    real_sleep = asyncio.sleep
    monkeypatch.setattr(gmaps.asyncio, "sleep", lambda s: real_sleep(0))
    cont = _contar_chamadas(monkeypatch)
    asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True))
    with psycopg.connect(pg) as con:
        con.execute("update cache set guardado_em = now() - interval '31 days' "
                    "where chave like 'gmaps|%%' or chave like 'osm|%%'")
    for k in cont:
        cont[k] = 0
    asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True))
    assert cont["gosom"] == 1 and cont["overpass"] > 0
    assert cont["osrm"] == 0  # a rota não venceu


def test_cache_quebrado_nao_derruba_a_coleta(mock_http, monkeypatch):
    import psycopg
    from app import banco

    def fora_do_ar():
        raise psycopg.OperationalError("connection refused")
    monkeypatch.setattr(banco, "URL", "postgresql://banco-fora-do-ar")
    monkeypatch.setattr(banco, "conectar", fora_do_ar)
    r = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200))
    assert r["paradas"][0]["cards"]


def test_sem_google_nao_tem_parcial(mock_http):
    parciais = []
    asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, parcial=parciais.append))
    assert parciais == []


def test_google_com_o_mesmo_lugar_enriquece_o_card_que_ja_foi():
    enviado = {"id": "osm:node/1", "nome": "Churrascaria Gaúcha", "fonte": "openstreetmap", "nota": None,
               "foto": None, "categoria": "restaurante"}
    do_google = {"id": "gmaps:P1", "nome": "Churrascaria Gaucha", "fonte": "google_maps", "nota": 4.7,
                 "avaliacoes": 1500, "foto": "https://lh5/x.jpg", "categoria": "restaurante"}
    novo = {"id": "gmaps:P2", "nome": "Café da Estrada", "fonte": "google_maps", "nota": 4.5}
    r = coletor._manter_enviados([do_google, novo], [enviado])
    assert [c["id"] for c in r] == ["osm:node/1", "gmaps:P2"]
    assert r[0]["nota"] == 4.7 and r[0]["foto"] == "https://lh5/x.jpg"
    assert r[0]["fonte"] == "openstreetmap+google_maps"


def test_card_do_parcial_que_saiu_do_corte_continua_no_final():
    enviado = {"id": "osm:node/9", "nome": "Posto Pequeno", "fonte": "openstreetmap"}
    r = coletor._manter_enviados([{"id": "gmaps:P3", "nome": "Posto Grande", "fonte": "google_maps"}], [enviado])
    assert [c["id"] for c in r] == ["gmaps:P3", "osm:node/9"]


def test_coleta_avisa_as_4_etapas_em_ordem(mock_http):
    etapas = []
    asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200,
                                        progresso=lambda *a: etapas.append(a)))
    ordem = [e[0] for e in etapas]
    assert [e for i, e in enumerate(ordem) if i == 0 or ordem[i - 1] != e] == ["rota", "cidades", "lugares", "instagram"]
    assert etapas[0][1:] == ("Rota calculada", "1.000 km, uns 14h de estrada", 20)
    assert etapas[1][1].endswith("para parar") and etapas[1][2] == "Uma a cada 200 km, mais o destino"
    lugares = [e for e in etapas if e[0] == "lugares"]
    assert lugares[0][2].endswith("agora · leva menos de 1 minuto")
    pct = [e[3] for e in etapas]
    assert pct == sorted(pct) and pct[-1] == 90


def test_veiculo_desconhecido_ou_aviao_da_422():
    from fastapi.testclient import TestClient
    from app.main import app
    from conftest import token
    cli = TestClient(app, headers={"Authorization": f"Bearer {token('00000000-0000-4000-8000-000000000001')}"})
    base = {"origem": "A, RS", "destino": "B, BA", "intervalo_km": 100}
    assert cli.post("/viagem", json={**base, "veiculo": "aviao"}).status_code == 422
    assert cli.post("/viagem", json={"origem": "A, RS", "destino": "B, BA"}).status_code == 422  # a pessoa escolhe o intervalo
    assert cli.post("/viagem", json={**base, "intervalo_km": 5}).status_code == 422
    assert cli.post("/viagem/aviao", json={"cidades": []}).status_code in (404, 405)
    assert cli.post("/roteiro/cidade", json={"cards": []}).status_code in (404, 405)


def test_api_job_inexistente(pessoa):
    from fastapi.testclient import TestClient
    from app.main import app
    _, cab = pessoa
    assert TestClient(app).get("/jobs/nao-existe", headers=cab).status_code == 404


def test_intervalo_curto_em_viagem_longa_respeita_o_teto_de_paradas():
    from app import coletor
    assert coletor.intervalo_efetivo(500, 100) == 100
    assert coletor.intervalo_efetivo(4000, 10) == 4000 / coletor.MAX_PARADAS
    assert 4000 / coletor.intervalo_efetivo(4000, 10) <= coletor.MAX_PARADAS


def test_mesmo_lugar_do_google_em_duas_categorias_aparece_uma_vez_na_parada():
    from app import coletor
    parada = {"nome": "Cidade", "uf": "BA", "lat": -12.0, "lon": -40.0, "raio_km": 8}
    parque = {"place_id": "P1", "nome": "Parque da Serra", "lat": -12.01, "lon": -40.01,
              "nota": 4.7, "avaliacoes": 900, "categoria_google": "Parque"}
    outro = {**parque, "place_id": "P2", "nome": "Mirante"}
    google = {"0|turismo": [parque], "0|natureza": [dict(parque), outro]}
    cards = coletor._escolher(0, parada, [], google, ["turismo", "natureza"], 5, 4.0)
    ids = [c["id"] for c in cards]
    assert ids == ["gmaps:P1", "gmaps:P2"]
    assert cards[0]["categoria"] == "turismo"


def test_busca_do_google_vazia_vale_so_um_dia(mock_http, monkeypatch, pg):
    import psycopg
    real_sleep = asyncio.sleep
    monkeypatch.setattr(gmaps.asyncio, "sleep", lambda s: real_sleep(0))
    asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True))
    with psycopg.connect(pg, autocommit=True) as con:
        vazias = con.execute("select count(*) from cache where chave like 'gmaps-vazio|%'").fetchone()[0]
        cheias = con.execute("select count(*) from cache where chave like 'gmaps|%' "
                             "and valor = '[]'::jsonb").fetchone()[0]
        assert vazias > 0 and cheias == 0  # vazio nunca entra na chave de 30 dias
        con.execute("update cache set guardado_em = now() - interval '2 days' where chave like 'gmaps-vazio|%'")
    geo._cache.clear()
    cont = _contar_chamadas(monkeypatch)
    asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Destino, BA", 200, usar_google_maps=True))
    assert cont["gosom"] == 1  # o vazio venceu: tenta o Google de novo
