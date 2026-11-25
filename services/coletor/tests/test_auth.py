"""Issue #3: autenticação pelo token do Supabase."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth, fila
from app.main import app
from conftest import token

UID = "00000000-0000-4000-8000-000000000001"
VIAGEM = {"origem": "A, RS", "destino": "B, BA", "intervalo_km": 100}


@pytest.mark.parametrize("metodo,rota,corpo", [
    ("post", "/viagem", VIAGEM),
    ("get", "/jobs/qualquer", None),
    ("post", "/swipe", {"card": {"id": "osm:node/1"}, "gostou": True}),
    ("delete", "/swipe/osm:node/1", None),
    ("get", "/perfil", None),
    ("post", "/triagem", {"respostas": []}),
    ("post", "/roteiro", {"cards": []}),
    ("post", "/cards/ranquear", {"cards": []}),
    ("post", "/eventos", {"evento": "roteiro_aberto_mapa", "viagem": UID, "app": "google"}),
])
def test_sem_token_da_401(metodo, rota, corpo):
    r = getattr(TestClient(app), metodo)(rota, **({"json": corpo} if corpo is not None else {}))
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("valor", [
    "Bearer ",
    "Basic abc",
    "Bearer nao-e-jwt",
    f"Bearer {token(UID, segundos=-120)}",                       # expirado
    f"Bearer {token(UID, aud='anon')}",                          # audiência errada
    f"Bearer {token('nao-e-uuid')}",
    "Bearer " + jwt.encode({"sub": UID, "aud": "authenticated", "exp": int(time.time()) + 60},
                           "outro-segredo-com-mais-de-32-caracteres!!", algorithm="HS256"),
    "Bearer " + jwt.encode({"sub": UID, "aud": "authenticated", "exp": int(time.time()) + 60},
                           None, algorithm="none"),
])
def test_token_invalido_da_401(valor):
    assert TestClient(app).get("/perfil", headers={"Authorization": valor}).status_code == 401


def test_usuario_sai_do_token_e_nao_do_corpo(pessoa):
    uid, cab = pessoa
    r = TestClient(app).post("/viagem", json={**VIAGEM, "usuario": "outra-pessoa"}, headers=cab)
    assert r.status_code == 202
    job = fila.pegar_proximo()
    assert job["entrada"]["usuario"] == uid


def test_job_de_outra_pessoa_da_404(pg):
    from conftest import criar_pessoa
    _, cab_dono = criar_pessoa(pg)
    _, cab_outro = criar_pessoa(pg)
    cli = TestClient(app)
    jid = cli.post("/viagem", json=VIAGEM, headers=cab_dono).json()["job_id"]
    assert cli.get(f"/jobs/{jid}", headers=cab_dono).status_code == 200
    assert cli.get(f"/jobs/{jid}", headers=cab_outro).status_code == 404


def test_perfil_e_swipe_sao_de_quem_esta_no_token(pg):
    from conftest import criar_pessoa
    _, cab_a = criar_pessoa(pg)
    _, cab_b = criar_pessoa(pg)
    cli = TestClient(app)
    assert cli.post("/swipe", json={"card": {"id": "osm:node/1", "categoria": "turismo"}, "gostou": True},
                    headers=cab_a).json()["ok"]
    assert cli.get("/perfil", headers=cab_a).json()["aceitos"] == 1
    assert cli.get("/perfil", headers=cab_b).json()["total_swipes"] == 0


def test_conta_sem_linha_em_usuario_e_criada_no_primeiro_uso(pg):
    """Conta criada antes da migração (sem a linha em usuario) não quebra o POST /viagem."""
    import uuid

    import psycopg
    uid = str(uuid.uuid4())
    with psycopg.connect(pg, autocommit=True) as con:
        con.execute("alter table auth.users disable trigger ao_criar_conta")
        con.execute("insert into auth.users (id) values (%s)", (uid,))
        con.execute("alter table auth.users enable trigger ao_criar_conta")
    r = TestClient(app).post("/viagem", json=VIAGEM, headers={"Authorization": f"Bearer {token(uid)}"})
    assert r.status_code == 202


def test_swipe_sem_id_da_422():
    r = TestClient(app).post("/swipe", json={"card": {"nome": "x"}, "gostou": True},
                             headers={"Authorization": f"Bearer {token(UID)}"})
    assert r.status_code == 422


def test_chave_assimetrica_pelo_jwks(monkeypatch):
    """Projetos novos do Supabase assinam com ES256; a chave pública vem do JWKS (simulado)."""
    privada = ec.generate_private_key(ec.SECP256R1())
    agora = int(time.time())
    url = "https://projeto.supabase.co"
    tok = jwt.encode({"sub": UID, "aud": "authenticated", "exp": agora + 60, "iss": f"{url}/auth/v1"},
                     privada, algorithm="ES256", headers={"kid": "k1"})

    class JwksFalso:
        def get_signing_key_from_jwt(self, t):
            assert jwt.get_unverified_header(t)["kid"] == "k1"
            return type("Chave", (), {"key": privada.public_key()})()

    monkeypatch.setattr(auth, "SUPABASE_URL", url)
    monkeypatch.setattr(auth, "_jwks", lambda u: JwksFalso())
    assert auth.validar(tok).id == UID
    outro = jwt.encode({"sub": UID, "aud": "authenticated", "exp": agora + 60, "iss": "https://outro/auth/v1"},
                       privada, algorithm="ES256", headers={"kid": "k1"})
    with pytest.raises(jwt.InvalidTokenError):
        auth.validar(outro)  # emissor de outro projeto


def test_cors_fechado_em_producao(monkeypatch):
    import importlib

    from app import main
    monkeypatch.setenv("PV_AMBIENTE", "producao")
    monkeypatch.delenv("PV_CORS_ORIGINS", raising=False)
    try:
        assert importlib.reload(main).ORIGENS == []
        monkeypatch.setenv("PV_CORS_ORIGINS", "https://desvio.app, https://x.dev")
        assert importlib.reload(main).ORIGENS == ["https://desvio.app", "https://x.dev"]
    finally:
        monkeypatch.delenv("PV_AMBIENTE")
        monkeypatch.delenv("PV_CORS_ORIGINS")
        importlib.reload(main)
