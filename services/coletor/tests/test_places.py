"""Places API (New) em gmaps.py, sem internet: o Google é simulado com httpx.MockTransport."""
import asyncio
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app import gmaps

CHAVE = "chave-de-teste"

LUGAR = {
    "id": "ChIJabc",
    "displayName": {"text": "Churrascaria Gaúcha", "languageCode": "pt-BR"},
    "primaryTypeDisplayName": {"text": "Churrascaria"},
    "formattedAddress": "Av. Brasil, 100 - Lages, SC",
    "location": {"latitude": -27.81, "longitude": -50.32},
    "googleMapsUri": "https://maps.google.com/?cid=123",
    "businessStatus": "OPERATIONAL",
    "rating": 4.7,
    "userRatingCount": 1834,
    "priceRange": {"startPrice": {"currencyCode": "BRL", "units": "50"},
                   "endPrice": {"currencyCode": "BRL", "units": "100"}},
    "priceLevel": "PRICE_LEVEL_MODERATE",
    "websiteUri": "https://www.instagram.com/churrascariagaucha/",
    "nationalPhoneNumber": "(49) 3222-0000",
    "regularOpeningHours": {"weekdayDescriptions": ["segunda-feira: 11:00–15:00, 18:00–23:00",
                                                    "domingo: Fechado"]},
    "photos": [
        {"name": "places/ChIJabc/photos/F1", "widthPx": 4000, "heightPx": 3000,
         "googleMapsUri": "https://maps.google.com/foto/F1",
         "authorAttributions": [{"displayName": "Ana", "uri": "https://maps.google.com/contrib/1",
                                 "photoUri": "https://lh3/ana"}]},
        {"name": "places/ChIJabc/photos/F2", "authorAttributions": []},
    ],
}


@pytest.fixture
def places(monkeypatch):
    monkeypatch.setenv("PV_GOOGLE_PLACES_KEY", CHAVE)
    pedidos: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        url = str(request.url)
        if url.endswith("/v1/places:searchText"):
            texto = json.loads(request.content)["textQuery"]
            if "quebra" in texto:
                return httpx.Response(500, json={"error": {"message": "interno"}})
            if "lento" in texto:
                raise httpx.ReadTimeout("demorou", request=request)
            if "vazio" in texto:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"places": [LUGAR, {"id": "semnome"}]})
        if "/media" in url:
            if "F404" in url:
                return httpx.Response(404, json={"error": {"message": "foto vencida"}})
            return httpx.Response(200, json={"name": "x", "photoUri": "https://lh3.googleusercontent.com/foto"})
        return httpx.Response(404)

    def rodar(coro_fn):
        async def _():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await coro_fn(client)
        return asyncio.run(_())

    rodar.pedidos = pedidos
    return rodar


# ---------- escolha da fonte ----------

def test_fonte_sem_chave_e_gosom():
    assert gmaps.fonte() == "gosom"


def test_fonte_com_chave_e_places(monkeypatch):
    monkeypatch.setenv("PV_GOOGLE_PLACES_KEY", CHAVE)
    assert gmaps.fonte() == "places"


def test_fonte_explicita_vence_a_chave(monkeypatch):
    monkeypatch.setenv("PV_GOOGLE_PLACES_KEY", CHAVE)
    monkeypatch.setenv("PV_GOOGLE_FONTE", "gosom")
    assert gmaps.fonte() == "gosom"
    monkeypatch.setenv("PV_GOOGLE_FONTE", "PLACES")
    assert gmaps.fonte() == "places"
    monkeypatch.setenv("PV_GOOGLE_FONTE", "outra")  # valor inválido: volta à regra da chave
    assert gmaps.fonte() == "places"


def test_places_sem_chave_avisa(monkeypatch):
    monkeypatch.setenv("PV_GOOGLE_FONTE", "places")
    with pytest.raises(gmaps.GoogleIndisponivel, match="PV_GOOGLE_PLACES_KEY"):
        asyncio.run(gmaps.buscar_lote(httpx.AsyncClient(), {"0|restaurante": "restaurantes em Lages, SC"}))


def test_nome_antigo_da_excecao_continua():
    assert gmaps.GosomIndisponivel is gmaps.GoogleIndisponivel
    assert issubclass(gmaps.GoogleIndisponivel, RuntimeError)


# ---------- Text Search ----------

def test_text_search_cabecalhos_e_corpo(places):
    places(lambda c: gmaps.buscar_lote(c, {"0|restaurante": "restaurantes em Lages, SC"}))
    (req,) = places.pedidos
    assert req.method == "POST" and str(req.url) == "https://places.googleapis.com/v1/places:searchText"
    assert req.headers["X-Goog-Api-Key"] == CHAVE
    mascara = req.headers["X-Goog-FieldMask"].split(",")
    assert all(m.startswith("places.") for m in mascara)
    assert "places.rating" in mascara and "places.photos" in mascara
    # nada de Atmosphere (mais caro) nem "*"
    assert not {"places.editorialSummary", "places.reviews", "places.allowsDogs", "*", "places.*"} & set(mascara)
    corpo = json.loads(req.content)
    assert corpo == {"textQuery": "restaurantes em Lages, SC", "languageCode": "pt-BR", "regionCode": "BR",
                     "pageSize": 20}


def test_mapeia_para_o_formato_do_gosom(places):
    r = places(lambda c: gmaps.buscar_lote(c, {"0|restaurante": "restaurantes em Lages, SC"}))
    (lugar,) = r["0|restaurante"]  # o lugar sem nome fica de fora
    assert set(lugar) == set(gmaps.linha_para_lugar({}))  # mesmas chaves das duas fontes
    assert lugar["input_id"] == "0|restaurante" and lugar["place_id"] == "ChIJabc"
    assert lugar["nome"] == "Churrascaria Gaúcha" and lugar["categoria_google"] == "Churrascaria"
    assert (lugar["nota"], lugar["avaliacoes"]) == (4.7, 1834)
    assert (lugar["lat"], lugar["lon"]) == (-27.81, -50.32)
    assert lugar["faixa_preco"] == "R$ 50–100"
    assert lugar["horarios"] == {"segunda-feira": ["11:00–15:00", "18:00–23:00"], "domingo": ["Fechado"]}
    assert lugar["status"] is None and lugar["link_maps"] == "https://maps.google.com/?cid=123"
    assert lugar["site"].startswith("https://www.instagram.com/") and lugar["telefone"] == "(49) 3222-0000"
    assert lugar["descricao"] is None and lugar["sobre"] == []


def test_fotos_vao_pelo_proxy_assinado_sem_chave(places):
    r = places(lambda c: gmaps.buscar_lote(c, {"0|restaurante": "restaurantes em Lages, SC"}))
    lugar = r["0|restaurante"][0]
    assert len(lugar["fotos"]) == 2 and lugar["foto"] == lugar["fotos"][0]
    assert lugar["foto"].startswith("/fotos/places/ChIJabc/photos/F1?l=800&ass=")
    assert all(CHAVE not in u for u in lugar["fotos"])
    assert lugar["fotos_autores"] == [[{"nome": "Ana", "uri": "https://maps.google.com/contrib/1",
                                        "avatar": "https://lh3/ana", "link_foto": "https://maps.google.com/foto/F1"}],
                                      []]


def test_url_publica_deixa_a_foto_absoluta(monkeypatch):
    monkeypatch.setenv("PV_GOOGLE_PLACES_KEY", CHAVE)
    monkeypatch.setenv("PV_API_URL_PUBLICA", "https://api.desvio.app/")
    assert gmaps.url_foto("places/A/photos/B").startswith("https://api.desvio.app/fotos/places/A/photos/B?l=800&ass=")


def test_status_preco_e_horario_ausentes():
    l = gmaps.place_para_lugar({"displayName": {"text": "X"}, "businessStatus": "CLOSED_PERMANENTLY",
                                "priceLevel": "PRICE_LEVEL_EXPENSIVE"}, "1|posto")
    assert l["status"] == "Fechado permanentemente" and l["faixa_preco"] == "$$$"
    assert l["horarios"] is None and l["foto"] is None and l["fotos"] == [] and l["lat"] is None


def test_consulta_que_falha_fica_de_fora_e_o_resto_volta(places):
    r = places(lambda c: gmaps.buscar_lote(c, {"a": "restaurantes em Lages, SC", "b": "quebra", "c": "lento",
                                               "d": "vazio"}))
    assert set(r) == {"a", "d"}  # b e c falharam: sem lista vazia, para o cache não guardar
    assert r["d"] == []


def test_todas_falham_vira_google_indisponivel(places):
    with pytest.raises(gmaps.GoogleIndisponivel):
        places(lambda c: gmaps.buscar_lote(c, {"b": "quebra", "c": "lento"}))


def test_lote_vazio_nao_chama_nada(places):
    assert places(lambda c: gmaps.buscar_lote(c, {})) == {}
    assert places.pedidos == []


# ---------- fotos ----------

def test_assinatura_da_foto(monkeypatch):
    monkeypatch.setenv("PV_GOOGLE_PLACES_KEY", CHAVE)
    url = gmaps.url_foto("places/A/photos/B", 400)
    ass = parse_qs(urlsplit(url).query)["ass"][0]
    assert gmaps.foto_valida("places/A/photos/B", 400, ass)
    assert not gmaps.foto_valida("places/A/photos/B", 800, ass)        # largura trocada
    assert not gmaps.foto_valida("places/A/photos/C", 400, ass)        # outra foto
    assert not gmaps.foto_valida("../../places:searchText", 400, ass)  # só nomes de foto
    monkeypatch.setenv("PV_GOOGLE_PLACES_KEY", "")
    assert not gmaps.foto_valida("places/A/photos/B", 400, ass)        # sem chave, sem foto


def test_url_da_foto_pede_sem_redirecionar(places):
    destino = places(lambda c: gmaps.url_da_foto(c, "places/ChIJabc/photos/F1", 800))
    assert destino == "https://lh3.googleusercontent.com/foto"
    (req,) = places.pedidos
    assert req.url.path == "/v1/places/ChIJabc/photos/F1/media"
    assert req.url.params["maxWidthPx"] == "800" and req.url.params["skipHttpRedirect"] == "true"
    assert req.headers["X-Goog-Api-Key"] == CHAVE


def test_url_da_foto_vencida_e_none(places):
    assert places(lambda c: gmaps.url_da_foto(c, "places/ChIJabc/photos/F404")) is None


def test_endpoint_fotos_redireciona_sem_token(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setenv("PV_GOOGLE_PLACES_KEY", CHAVE)
    pedidos = []

    async def falsa(client, nome, largura):
        pedidos.append((nome, largura))
        return "https://lh3.googleusercontent.com/foto" if nome.endswith("F1") else None
    monkeypatch.setattr(gmaps, "url_da_foto", falsa)
    cli = TestClient(main.app)  # sem Authorization: o <Image> do app não manda cabeçalho

    r = cli.get(gmaps.url_foto("places/ChIJabc/photos/F1"), follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://lh3.googleusercontent.com/foto"
    assert CHAVE not in r.headers["location"]
    assert cli.get(gmaps.url_foto("places/ChIJabc/photos/F9"), follow_redirects=False).status_code == 404
    falsificada = "/fotos/places/ChIJabc/photos/F1?l=800&ass=" + "0" * 32
    assert cli.get(falsificada, follow_redirects=False).status_code == 404
    assert pedidos == [("places/ChIJabc/photos/F1", 800), ("places/ChIJabc/photos/F9", 800)]
