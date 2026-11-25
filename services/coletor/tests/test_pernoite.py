"""Issue #104: pernoite planejado na coleta, com hotéis nas cidades onde a pessoa dorme."""
import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest

from app import coletor, geo, gmaps, instagram, pernoite, roteiro

# ---------- onde cada dia acaba ----------


def test_pontos_de_pernoite_de_carro_saindo_as_7h():
    """31 h de estrada, 9 h por dia: dorme depois de 9, 18 e 27 h; o 4º dia chega."""
    noites = pernoite.pontos(31, 2800, "carro", "07:00")
    assert [(n["dia"], n["horas_desde_saida"]) for n in noites] == [(1, 9), (2, 18), (3, 27)]
    assert [round(n["km"]) for n in noites] == [813, 1626, 2439]


def test_pontos_de_pernoite_pelo_veiculo_e_pela_saida():
    assert [n["horas_desde_saida"] for n in pernoite.pontos(13, 600, "bicicleta", "07:00")] == [6, 12]
    assert pernoite.pontos(8.5, 700, "carro", "07:00") == []  # cabe num dia: nenhuma noite
    # saindo às 20h só dá 2 h até as 22h; os dias seguintes começam às 8h
    assert [n["horas_desde_saida"] for n in pernoite.pontos(12, 900, "carro", "20:00")] == [2, 11]
    # saindo depois das 22h, o primeiro dia não roda: a primeira noite é a do dia 2
    assert [n["dia"] for n in pernoite.pontos(12, 900, "carro", "23:00")] == [2]
    assert pernoite.pontos(0, 0) == []


def test_sem_saida_vale_as_7h():
    assert pernoite.pontos(20, 1500, "carro") == pernoite.pontos(20, 1500, "carro", "07:00")


# ---------- escolha da cidade ----------


def _parada(nome, km, tipo="parada"):
    return {"nome": nome, "uf": "SC", "lat": 0.0, "lon": km / 100, "tipo": tipo, "km_na_rota": km}


def test_parada_perto_vira_estadia_e_a_longe_nao():
    paradas = [_parada("A", 200), _parada("B", 410), _parada("C", 600)]
    faltam = pernoite.marcar(paradas, [{"dia": 1, "km": 400}, {"dia": 2, "km": 800}], folga=20)
    assert [p["tipo"] for p in paradas] == ["parada", "estadia", "parada"] and paradas[1]["dia"] == 1
    assert faltam == [{"dia": 2, "km": 800}]


def test_folga_sai_do_intervalo(monkeypatch):
    monkeypatch.setattr(pernoite, "FOLGA_PCT", 10.0)
    assert pernoite.folga_km(200) == 20
    monkeypatch.setattr(pernoite, "FOLGA_PCT", 25.0)
    assert pernoite.folga_km(200) == 50


def _planejar(paradas, noites, cidades):
    """`cidades`: km do ponto perguntado -> cidade (ou None); devolve os kms perguntados."""
    perguntas = []

    async def achar(ponto):
        km = ponto[1] * 100
        perguntas.append(round(km))
        return cidades.get(round(km))

    asyncio.run(pernoite.planejar(paradas, noites, intervalo_km=200, ponto_do_km=lambda km: (0.0, km / 100),
                                  km_do_ponto=lambda p: p[1] * 100, achar_cidade=achar,
                                  excluir={"origem"}))
    return perguntas


def test_sem_parada_perto_insere_a_cidade_do_ponto_na_ordem_do_km():
    paradas = [_parada("A", 200), _parada("C", 600), _parada("Destino", 1000, "destino")]
    cidade = {"nome": "Nova", "uf": "PR", "lat": 0.0, "lon": 4.05, "raio_km": 8}
    assert _planejar(paradas, [{"dia": 1, "km": 400}], {400: cidade}) == [400]
    assert [p["nome"] for p in paradas] == ["A", "Nova", "C", "Destino"]
    nova = paradas[1]
    assert (nova["tipo"], nova["dia"], nova["km_na_rota"], nova["uf"]) == ("estadia", 1, 405, "PR")


def test_sem_cidade_no_ponto_tenta_antes_dele():
    paradas = [_parada("Destino", 1000, "destino")]
    antes = {"nome": "Antes", "uf": "PR", "lat": 0.0, "lon": 3.5, "raio_km": 8}
    # sem cidade no km 400 nem a origem (excluída) no 350: fica a do km 300
    perguntas = _planejar(paradas, [{"dia": 1, "km": 400}],
                          {400: None, 350: {"nome": "Origem", "lat": 0, "lon": 3.5}, 300: antes})
    assert perguntas == [400, 350, 300]
    assert paradas[0]["nome"] == "Antes" and paradas[0]["tipo"] == "estadia"


def test_cidade_do_ponto_que_ja_e_parada_vira_estadia_sem_repetir():
    paradas = [_parada("A", 200), _parada("B", 470)]
    _planejar(paradas, [{"dia": 1, "km": 400}], {400: {"nome": "B", "lat": 0, "lon": 4.7}})
    assert [(p["nome"], p["tipo"]) for p in paradas] == [("A", "parada"), ("B", "estadia")]


def test_hospedagem_sempre_na_estadia_e_so_nela():
    cats = ["turismo", "restaurante"]
    assert pernoite.categorias_da_parada({"tipo": "estadia"}, cats) == ["hospedagem", "turismo", "restaurante"]
    assert pernoite.categorias_da_parada({"tipo": "parada"}, cats) == cats
    assert pernoite.categorias_da_parada({"tipo": "destino"}, cats) == cats
    marcada = ["restaurante", "hospedagem"]
    assert pernoite.categorias_da_parada({"tipo": "estadia"}, marcada) == ["hospedagem", "restaurante"]
    assert pernoite.categorias_da_parada({"tipo": "parada"}, marcada) == marcada


def test_hoteis_primeiro_so_na_estadia():
    cards = [{"id": "r", "categoria": "restaurante"}, {"id": "h1", "categoria": "hospedagem"},
             {"id": "t", "categoria": "turismo"}, {"id": "h2", "categoria": "hospedagem"}]
    paradas = [{"tipo": "estadia", "cards": list(cards)}, {"tipo": "parada", "cards": list(cards)}]
    pernoite.hoteis_primeiro(paradas)
    assert [c["id"] for c in paradas[0]["cards"]] == ["h1", "h2", "r", "t"]
    assert [c["id"] for c in paradas[1]["cards"]] == ["r", "h1", "t", "h2"]


# ---------- coleta inteira, sem internet: Alegrete -> Vitória da Conquista ----------

ALEGRETE, CONQUISTA = (-29.78, -55.79), (-14.86, -40.84)
ROTA = [(ALEGRETE[0] + (CONQUISTA[0] - ALEGRETE[0]) * i / 100, ALEGRETE[1] + (CONQUISTA[1] - ALEGRETE[1]) * i / 100)
        for i in range(101)]


class Servicos:
    """Nominatim, OSRM, Overpass e Places API simulados; anota onde a hospedagem foi buscada."""

    def __init__(self):
        self.cidades: dict[str, tuple[float, float]] = {}
        self.overpass_hotel: list[tuple[float, float]] = []
        self.overpass_sem_hotel: list[tuple[float, float]] = []
        self.places: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "nominatim" in url and "/reverse" in url:
            return httpx.Response(200, json={"address": {"city": "X", "ISO3166-2-lvl4": "BR-MG"}})
        if "router.project-osrm.org" in url:
            # 2.800 km e 31 h de carro, como o OSRM dá para essa viagem
            return httpx.Response(200, json={"code": "Ok", "routes": [{"distance": 2_800_000, "duration": 111_600,
                                  "geometry": {"coordinates": [[lo, la] for la, lo in ROTA]}}]})
        if "overpass" in url:
            corpo = parse_qs(request.content.decode())["data"][0]
            lat, lon = (float(x) for x in corpo.split("around:")[1].split(")")[0].split(",")[1:3])
            if '"place"' in corpo:
                nome = f"Cidade{lat:.2f}"
                self.cidades[nome] = (lat + 0.01, lon)
                return httpx.Response(200, json={"elements": [{"type": "node", "id": 1, "lat": lat + 0.01, "lon": lon,
                                                               "tags": {"name": nome, "population": "50000"}}]})
            elementos = [{"type": "node", "id": 10, "lat": lat, "lon": lon, "tags": {"name": "Posto", "amenity": "fuel"}},
                         {"type": "node", "id": 11, "lat": lat, "lon": lon,
                          "tags": {"name": "Cantina", "amenity": "restaurant"}}]
            if "hotel" in corpo:
                self.overpass_hotel.append((lat, lon))
                elementos.append({"type": "node", "id": 12, "lat": lat, "lon": lon,
                                  "tags": {"name": "Pousada da Estrada", "tourism": "guest_house"}})
            else:
                self.overpass_sem_hotel.append((lat, lon))
            return httpx.Response(200, json={"elements": elementos})
        if url == "https://places.googleapis.com/v1/places:searchText":
            texto = json.loads(request.content)["textQuery"]
            self.places.append(texto)
            if not texto.startswith("hotéis em "):
                return httpx.Response(200, json={})
            cidade = texto.removeprefix("hotéis em ").split(",")[0]
            lat, lon = self.cidades.get(cidade, CONQUISTA)
            return httpx.Response(200, json={"places": [{
                "id": f"H{cidade}", "displayName": {"text": f"Hotel {cidade}"},
                "location": {"latitude": lat, "longitude": lon}, "rating": 4.5, "userRatingCount": 300}]})
        return httpx.Response(404)


@pytest.fixture
def servicos(monkeypatch):
    s = Servicos()
    original = httpx.AsyncClient

    class Cliente(original):
        def __init__(self, *a, **k):
            k["transport"] = httpx.MockTransport(s)
            super().__init__(*a, **k)

    monkeypatch.setattr(httpx, "AsyncClient", Cliente)
    monkeypatch.setattr(coletor.httpx, "AsyncClient", Cliente)
    real_sleep = asyncio.sleep
    monkeypatch.setattr(geo.asyncio, "sleep", lambda _s: real_sleep(0))
    monkeypatch.setattr(gmaps.asyncio, "sleep", lambda _s: real_sleep(0))
    monkeypatch.setenv("PV_GOOGLE_PLACES_KEY", "chave-de-teste")
    geo._cache.clear()
    return s


def _alegrete_conquista(**kw):
    return asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Vitória da Conquista, BA", 200,
                                               categorias=["turismo", "restaurante", "posto"],
                                               usar_google_maps=True, buscar_instagram=False,
                                               veiculo="carro", saida="07:00", **kw))


def test_alegrete_a_conquista_de_carro_dorme_em_cidades_com_hotel(servicos):
    r = _alegrete_conquista()
    estadias = [p for p in r["paradas"] if p["tipo"] == "estadia"]
    assert 2 <= len(estadias) <= 3, [p["nome"] for p in estadias]
    assert len(estadias) == 3  # 31 h: dorme depois de 9, 18 e 27 h
    assert [p["dia"] for p in estadias] == list(range(1, len(estadias) + 1))
    # cada noite perto de onde o dia acaba: 9, 18 e 27 h de estrada (folga de um intervalo)
    for p, horas in zip(estadias, (9, 18, 27)):
        assert abs(p["horas_desde_saida"] - horas) <= 31 * 200 / r["rota"]["distancia_km"] + 0.1
    for p in estadias:
        assert p["cards"][0]["categoria"] == "hospedagem"  # onde dormir vem primeiro
        nomes = {c["nome"] for c in p["cards"] if c["categoria"] == "hospedagem"}
        assert {f'Hotel {p["nome"]}', "Pousada da Estrada"} <= nomes
    # as paradas continuam na ordem do km, com o destino no fim
    kms = [p["km_na_rota"] for p in r["paradas"]]
    assert kms == sorted(kms) and r["paradas"][-1]["tipo"] == "destino"


def test_hotel_so_e_buscado_nas_cidades_de_pernoite(servicos):
    r = _alegrete_conquista()
    estadias = {p["nome"] for p in r["paradas"] if p["tipo"] == "estadia"}
    outras = {p["nome"] for p in r["paradas"] if p["tipo"] != "estadia"}
    hoteis_google = {t.removeprefix("hotéis em ").split(",")[0] for t in servicos.places if t.startswith("hotéis em ")}
    assert hoteis_google == estadias
    assert len(servicos.overpass_hotel) == len(estadias)
    assert len(servicos.overpass_sem_hotel) == len(outras)
    for p in r["paradas"]:
        if p["tipo"] != "estadia":
            assert all(c["categoria"] != "hospedagem" for c in p["cards"])


def test_com_hospedagem_marcada_todas_as_paradas_tem_hotel(servicos):
    r = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Vitória da Conquista, BA", 200,
                                            categorias=["restaurante", "hospedagem"], usar_google_maps=True,
                                            buscar_instagram=False, saida="07:00"))
    assert len(servicos.overpass_hotel) == len(r["paradas"]) and not servicos.overpass_sem_hotel


def test_saida_tarde_muda_onde_dorme(servicos):
    cedo = _alegrete_conquista()
    servicos.__init__()
    tarde = asyncio.run(coletor.planejar_viagem("Alegrete, RS", "Vitória da Conquista, BA", 200,
                                                usar_google_maps=True, buscar_instagram=False, saida="18:00"))
    primeira = lambda r: next(p for p in r["paradas"] if p["tipo"] == "estadia")
    # saindo às 18h, o primeiro dia só tem 4 h até as 22h
    assert primeira(tarde)["horas_desde_saida"] < primeira(cedo)["horas_desde_saida"]


# ---------- roteiro: o hotel de cada noite ----------

ESTADIAS = [{"ordem": 2, "nome": "Lages", "uf": "SC", "dia": 1, "horas_desde_saida": 9.0},
            {"ordem": 5, "nome": "Registro", "uf": "SP", "dia": 2, "horas_desde_saida": 18.0}]


def _lugar(i, horas, categoria="turismo", cidade="Outra"):
    return {"id": f"l{i}", "nome": f"Lugar {i}", "categoria": categoria, "cidade": cidade,
            "horas_desde_saida": horas, "km_na_rota": horas * 80}


def test_agenda_dorme_nas_estadias_planejadas():
    itens = [_lugar(1, 3), _lugar(2, 8.9, "hospedagem", "Lages"), _lugar(3, 9.0, "restaurante", "Lages"),
             _lugar(4, 12), _lugar(5, 20)]
    agenda = roteiro.agendar(roteiro.ordenar_na_rota(itens, ESTADIAS), "07:00", "carro", estadias=ESTADIAS)
    # o hotel fica no fim do dia 1, depois do jantar na mesma cidade
    assert [(c["id"], c["dia"], c["chegada"], c["pernoite"]) for c in agenda] == [
        ("l1", 1, "10:00", False), ("l3", 1, "17:00", False), ("l2", 1, "18:06", True),
        ("l4", 2, "10:00", False),  # o dia 2 sai de Lages às 7h: 3 h até o l4
        ("l5", 3, "09:00", False),  # o dia 3 sai de Registro: 2 h até o l5
    ]


def test_noite_sem_hotel_avisa_o_que_falta():
    itens = roteiro.agendar([_lugar(1, 3), _lugar(2, 9, "hospedagem", "Lages"), _lugar(3, 12)], "07:00",
                            estadias=ESTADIAS)
    assert roteiro.noites(itens, ESTADIAS) == [
        {"dia": 1, "cidade": "Lages", "uf": "SC", "parada": 2,
         "hotel": {"id": "l2", "nome": "Lugar 2"}, "aviso": None},
        {"dia": 2, "cidade": "Registro", "uf": "SP", "parada": 5, "hotel": None,
         "aviso": "Falta escolher onde dormir em Registro"},
    ]
    assert roteiro.noites(itens, []) == []


def test_sem_estadias_a_agenda_continua_a_do_95():
    itens = [_lugar(1, 2), _lugar(2, 7, "restaurante"), _lugar(3, 12)]
    assert roteiro.agendar(itens, "07:00", estadias=[]) == roteiro.agendar(itens, "07:00")


# ---------- API: saída na viagem e noites no roteiro (com banco) ----------


def _coleta_com_estadia(cards_lages, cards_destino):
    return {"veiculo": "carro", "intervalo_km": 200,
            "rota": {"distancia_km": 1200, "duracao_h": 15, "polilinha": [[-29.78, -55.79], [-25.0, -48.0]]},
            "paradas": [
                {"nome": "Lages", "uf": "SC", "lat": -27.8, "lon": -50.3, "tipo": "estadia", "dia": 1,
                 "raio_km": 8, "km_na_rota": 720, "horas_desde_saida": 9.0, "cards": cards_lages},
                {"nome": "Curitiba", "uf": "PR", "lat": -25.4, "lon": -49.3, "tipo": "destino",
                 "raio_km": 15, "km_na_rota": 1200, "horas_desde_saida": 15.0, "cards": cards_destino},
            ]}


def _card(i, categoria, cidade, horas):
    return {"id": f"osm:node/{i}", "nome": f"Lugar {i}", "categoria": categoria, "cidade": cidade,
            "fonte": "openstreetmap", "lat": -27.8, "lon": -50.3, "km_na_rota": horas * 80,
            "horas_desde_saida": horas}


def test_viagem_guarda_saida_e_data_e_o_roteiro_avisa_a_noite_sem_hotel(pg, monkeypatch):
    from fastapi.testclient import TestClient

    from app import ia, worker
    from app.main import app
    from conftest import criar_pessoa

    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    pedido = {"origem": "Alegrete, RS", "destino": "Curitiba, PR", "intervalo_km": 200,
              "saida": "06:30", "data": "2026-12-20"}
    assert cli.post("/viagem", json={**pedido, "saida": "25:00"}, headers=cab).status_code == 422
    resp = cli.post("/viagem", json=pedido, headers=cab)
    assert resp.status_code == 202
    vid = resp.json()["viagem_id"]
    [v] = cli.get("/viagens", headers=cab).json()["viagens"]
    assert (v["saida"], v["data"]) == ("06:30", "2026-12-20")

    entradas = []
    hotel, jantar, museu = (_card(1, "hospedagem", "Lages", 9.0), _card(2, "restaurante", "Lages", 9.0),
                            _card(3, "turismo", "Curitiba", 15.0))

    async def coleta(progresso=None, parcial=None, **kw):
        entradas.append(kw)
        return _coleta_com_estadia([jantar, hotel], [museu])
    monkeypatch.setattr(worker.coletor, "planejar_viagem", coleta)
    assert asyncio.run(worker.rodar_uma_vez()) is True
    assert (entradas[0]["saida"], entradas[0]["data"]) == ("06:30", "2026-12-20")  # a coleta recebe a saída

    [lages, _] = cli.get(f"/viagens/{vid}", headers=cab).json()["paradas"]
    assert (lages["tipo"], lages["dia"]) == ("estadia", 1)
    assert lages["cards"][0]["id"] == hotel["id"]  # na estadia, o hotel vem primeiro

    for c in (jantar, museu):
        cli.post("/swipe", json={"card": c, "tipo": "bora", "viagem": vid, "parada": 0}, headers=cab)
    pedidos = []

    async def groq_fora(client, **kw):
        pedidos.append(kw["dados"])
        raise ia.IAIndisponivel("teste")
    monkeypatch.setattr(ia, "chamar_json", groq_fora)
    corpo = cli.post(f"/viagens/{vid}/roteiro", headers=cab, json={"usar_ia": True}).json()
    assert pedidos[0]["contexto"] == {"saida": "06:30", "data": "2026-12-20"}  # padrão da viagem
    assert corpo["noites"] == [{"dia": 1, "cidade": "Lages", "uf": "SC", "parada": 0, "hotel": None,
                                "aviso": "Falta escolher onde dormir em Lages"}]
    assert [(c["id"], c["dia"]) for c in corpo["itens"]] == [(jantar["id"], 1), (museu["id"], 2)]

    cli.post("/swipe", json={"card": hotel, "tipo": "bora", "viagem": vid, "parada": 0}, headers=cab)
    corpo = cli.post(f"/viagens/{vid}/roteiro", headers=cab, json={"usar_ia": True}).json()
    assert corpo["noites"][0]["hotel"] == {"id": hotel["id"], "nome": "Lugar 1"} and corpo["noites"][0]["aviso"] is None
    # o hotel fecha o dia 1, depois do jantar na mesma cidade, e é o pernoite
    assert [(c["id"], c["dia"], c["pernoite"]) for c in corpo["itens"]] == [
        (jantar["id"], 1, False), (hotel["id"], 1, True), (museu["id"], 2, False)]

    # a ordem da pessoa (PUT) também traz as noites
    editado = cli.put(f"/viagens/{vid}/roteiro", headers=cab, json={"itens": [jantar["id"], museu["id"]]}).json()
    assert editado["noites"][0]["aviso"] == "Falta escolher onde dormir em Lages"


def test_viagem_sem_saida_vale_as_7h(pg):
    from fastapi.testclient import TestClient

    from app.main import app
    from conftest import criar_pessoa

    _, cab = criar_pessoa(pg)
    cli = TestClient(app)
    cli.post("/viagem", json={"origem": "Alegrete, RS", "destino": "Curitiba, PR", "intervalo_km": 200}, headers=cab)
    [v] = cli.get("/viagens", headers=cab).json()["viagens"]
    assert (v["saida"], v["data"]) == ("07:00", None)
