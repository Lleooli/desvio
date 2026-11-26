"""Issue #42: duração das etapas no log e eventos de erro sem dado pessoal."""
import asyncio
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app import fila, observabilidade, worker
from app.main import app


def _eventos(caplog) -> list[dict]:
    linhas = []
    for rec in caplog.records:
        if rec.name != "desvio.observabilidade":
            continue
        linhas.append(json.loads(rec.message))
    return linhas


def test_antes_de_enviar_tira_token_email_e_coordenada():
    evento = {
        "message": "falhou para ana@exemplo.com com Bearer abc.def.ghi",
        "user": {"id": "uuid", "email": "ana@exemplo.com", "ip_address": "1.2.3.4"},
        "request": {
            "headers": {"Authorization": "Bearer segredo", "Cookie": "sessao=1", "content-type": "application/json"},
            "cookies": {"sessao": "1"},
            "data": {"email": "ana@exemplo.com", "origem": "Rua da Casa, 10", "lat": -29.7, "lon": -55.8},
            "env": {"HTTP_COOKIE": "sessao=1"},
        },
    }
    limpo = observabilidade.antes_de_enviar(evento, {})
    texto = json.dumps(limpo)
    assert "user" not in limpo
    assert "Authorization" not in limpo["request"]["headers"]
    assert "Cookie" not in limpo["request"]["headers"]
    assert limpo["request"]["headers"]["content-type"] == "application/json"
    assert "data" not in limpo["request"]
    assert "cookies" not in limpo["request"]
    assert "ana@exemplo.com" not in texto
    assert "Bearer abc" not in texto
    assert "segredo" not in texto
    assert "-29.7" not in texto
    assert "[e-mail]" in texto
    assert "Bearer [token]" in texto


def test_iniciar_grava_release_e_environment_sem_pii(monkeypatch):
    import sentry_sdk
    from sentry_sdk.transport import Transport

    class SemRede(Transport):
        def capture_envelope(self, envelope):
            return None

    monkeypatch.setattr(observabilidade, "_transporte", SemRede)
    monkeypatch.setenv("SENTRY_DSN", "https://chave@o0.ingest.sentry.io/1")
    monkeypatch.setenv("PV_AMBIENTE", "staging")
    monkeypatch.setenv("PV_RELEASE", "desvio@0.1.0")
    observabilidade.iniciar()
    cliente = sentry_sdk.get_client()
    assert cliente.options["release"] == "desvio@0.1.0"
    assert cliente.options["environment"] == "staging"
    assert cliente.options["send_default_pii"] is False
    assert cliente.options["max_request_body_size"] == "never"
    assert cliente.options["before_send"] is observabilidade.antes_de_enviar
    observabilidade.desligar()


def test_erro_real_nao_leva_variavel_local_nem_endereco(monkeypatch):
    from sentry_sdk.transport import Transport

    enviados = []

    class Guarda(Transport):
        def capture_envelope(self, envelope):
            enviados.append(b"".join(item.get_bytes() for item in envelope.items))

    monkeypatch.setattr(observabilidade, "_transporte", Guarda)
    monkeypatch.setenv("SENTRY_DSN", "https://chave@o0.ingest.sentry.io/1")
    observabilidade.iniciar()
    # Montados na hora: o Sentry manda as linhas do código-fonte em volta do erro, e o teste
    # quer saber dos VALORES das variáveis, não do texto do arquivo.
    segredo = "-".join(["gsk", "segredo", "do", "groq"])
    endereco = " ".join(["Rua", "da", "Casa,", "10"])
    try:
        chave = segredo  # noqa: F841 (é o que não pode sair)
        entrada = {"origem": endereco}  # noqa: F841
        raise RuntimeError("falhou a coleta")
    except RuntimeError:
        observabilidade.capturar()
    import sentry_sdk
    sentry_sdk.flush()
    observabilidade.desligar()
    texto = b"".join(enviados).decode("utf-8", "replace")
    assert "falhou a coleta" in texto
    assert segredo not in texto
    assert endereco not in texto
    assert '"sdk"' in texto and "sentry.python" in texto  # o nome do SDK não some mais


def test_linha_de_etapa_sai_como_json_puro(capsys):
    log = observabilidade.log
    antes = (list(log.handlers), log.propagate, log.level)
    try:
        observabilidade.configurar_log()
        observabilidade.configurar_log()  # chamar de novo não duplica a linha
        log.setLevel("INFO")
        observabilidade.linha("job1", "rota", "concluido", 12.4)
    finally:
        log.handlers[:], log.propagate = antes[0], antes[1]
        log.setLevel(antes[2])
    saida = [l for l in capsys.readouterr().err.splitlines() if l]
    assert saida == ['{"evento": "etapa_busca", "job_id": "job1", "etapa": "rota", "status": "concluido", "duracao_ms": 12}']


def test_sem_dsn_nao_liga_o_sentry(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    observabilidade.desligar()
    observabilidade.iniciar()
    assert observabilidade._ativo is False


def test_rota_de_teste_so_em_staging_com_token(monkeypatch):
    monkeypatch.setenv("PV_ADMIN_TOKEN", "segredo")
    cli = TestClient(app, raise_server_exceptions=False)
    monkeypatch.setenv("PV_AMBIENTE", "producao")
    assert cli.get("/observabilidade/teste", headers={"x-admin-token": "segredo"}).status_code == 404
    monkeypatch.delenv("PV_AMBIENTE", raising=False)
    assert cli.get("/observabilidade/teste", headers={"x-admin-token": "segredo"}).status_code == 404
    monkeypatch.setenv("PV_AMBIENTE", "staging")
    assert cli.get("/observabilidade/teste").status_code == 404
    assert cli.get("/observabilidade/teste", headers={"x-admin-token": "errado"}).status_code == 404
    resposta = cli.get("/observabilidade/teste", headers={"x-admin-token": "segredo"})
    assert resposta.status_code == 500
    assert "segredo" not in resposta.text
    assert "@" not in resposta.text


def test_job_registra_duracao_de_cada_etapa(pg, monkeypatch, caplog):
    import app.coletor as coletor
    import app.gmaps as gmaps
    import app.instagram as instagram

    async def cidade(client, lugar):
        return {"nome": "Cidade", "uf": "RS", "lat": -29.78, "lon": -55.79}

    async def rota(client, origem, destino, veiculo="carro"):
        return {"pontos": [origem, destino], "distancia_km": 10, "duracao_h": 0.2}

    async def sem_pernoite(*a, **k):
        return None

    async def sem_pois(*a, **k):
        return []

    async def sem_wiki(*a, **k):
        return None

    async def sem_instagram(*a, **k):
        return None

    async def google(client, faltam):
        return {chave: [] for chave in faltam}

    monkeypatch.setattr(coletor.geo, "geocodificar", cidade)
    monkeypatch.setattr(coletor.geo, "rota", rota)
    monkeypatch.setattr(coletor, "_planejar_pernoites", sem_pernoite)
    monkeypatch.setattr(coletor, "_pois_com_cache", sem_pois)
    monkeypatch.setattr(coletor, "_completar_wikipedia", sem_wiki)
    monkeypatch.setattr(instagram, "completar", sem_instagram)
    monkeypatch.setattr(gmaps, "buscar_lote", google)
    monkeypatch.setattr(worker.viagens, "gravar_resultado", lambda *a, **k: None)

    uid_viagem = "11111111-1111-4111-8111-111111111111"
    fila.criar("viagem", {
        "origem": "Origem, RS", "destino": "Destino, BA", "intervalo_km": 500,
        "usar_google_maps": True, "buscar_instagram": False, "viagem": uid_viagem,
    })
    caplog.set_level(logging.INFO, logger="desvio.observabilidade")
    assert asyncio.run(worker.rodar_uma_vez()) is True

    concluidas = [e for e in _eventos(caplog) if e["status"] == "concluido"]
    por_etapa = {e["etapa"]: e for e in concluidas}
    for etapa in ("rota", "cidades", "osm", "google", "ranqueamento", "job"):
        assert etapa in por_etapa, etapa
        assert isinstance(por_etapa[etapa]["duracao_ms"], int)
        assert por_etapa[etapa]["job_id"]
        assert por_etapa[etapa]["evento"] == "etapa_busca"
    assert por_etapa["job"]["viagem_id"] == uid_viagem
    texto = " ".join(rec.message for rec in caplog.records if rec.name == "desvio.observabilidade")
    assert "Origem, RS" not in texto
    assert "@" not in texto
    assert "Bearer" not in texto
    assert "-29.78" not in texto


def test_job_que_falha_registra_falha_e_captura(pg, monkeypatch, caplog):
    capturadas = []

    async def quebra(job):
        raise RuntimeError("coleta para ana@exemplo.com")

    monkeypatch.setattr(worker, "processar", quebra)
    monkeypatch.setattr(observabilidade, "capturar", lambda: capturadas.append("sim"))
    fila.criar("viagem", {"origem": "A", "destino": "B", "viagem": "v1"})
    caplog.set_level(logging.INFO, logger="desvio.observabilidade")
    assert asyncio.run(worker.rodar_uma_vez()) is True
    falhas = [e for e in _eventos(caplog) if e["etapa"] == "job" and e["status"] == "falha"]
    assert len(falhas) == 1
    assert isinstance(falhas[0]["duracao_ms"], int)
    assert capturadas == ["sim"]
    assert "ana@exemplo.com" not in falhas[0].get("evento", "")
    assert "ana@" not in json.dumps(falhas)
