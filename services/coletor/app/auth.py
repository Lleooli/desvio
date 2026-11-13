"""Autenticação pelo token do Supabase (Authorization: Bearer <access_token>).

O app entra pelo Supabase Auth (Google, Apple ou link por e-mail) e manda o
access_token em toda requisição. A API valida a assinatura e tira o usuário do
`sub`; o usuário nunca vem do corpo da requisição.

Duas formas de assinatura, conforme o projeto do Supabase:
- chaves assimétricas (ES256/RS256, padrão nos projetos novos): a chave pública
  vem de SUPABASE_URL/auth/v1/.well-known/jwks.json, com cache;
- segredo compartilhado (HS256, projetos antigos): SUPABASE_JWT_SECRET.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
AUDIENCIA = "authenticated"


@dataclass(frozen=True)
class Usuario:
    id: str
    email: str | None = None


class ChavesIndisponiveis(RuntimeError):
    """Não deu para buscar o JWKS do Supabase (falha de rede); a API responde 503, não 401."""


@lru_cache(maxsize=1)
def _jwks(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json", cache_keys=True, lifespan=3600)


def validar(token: str) -> Usuario:
    """Usuário do token, ou jwt.InvalidTokenError (ChavesIndisponiveis se o JWKS não responde)."""
    alg = jwt.get_unverified_header(token).get("alg")
    if alg == "HS256":
        if not JWT_SECRET:
            raise jwt.InvalidTokenError("HS256 sem SUPABASE_JWT_SECRET")
        chave = JWT_SECRET
    elif alg in ("ES256", "RS256"):
        if not SUPABASE_URL:
            raise jwt.InvalidTokenError("sem SUPABASE_URL para buscar as chaves públicas")
        try:
            chave = _jwks(SUPABASE_URL).get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError as e:  # rede: o token pode estar ótimo
            raise ChavesIndisponiveis(str(e)) from e
        except jwt.PyJWKClientError as e:
            raise jwt.InvalidTokenError(str(e)) from e
    else:
        raise jwt.InvalidTokenError(f"algoritmo não aceito: {alg}")
    opcoes = {"require": ["sub", "exp"]}
    emissor = f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else None
    dados = jwt.decode(token, chave, algorithms=[alg], audience=AUDIENCIA, issuer=emissor, options=opcoes,
                       leeway=30)
    try:
        uid = str(uuid.UUID(dados["sub"]))
    except (ValueError, TypeError, AttributeError):
        raise jwt.InvalidTokenError("sub não é um id de usuário") from None
    return Usuario(id=uid, email=dados.get("email"))


def usuario_atual(authorization: str | None = Header(None)) -> Usuario:
    """Dependência do FastAPI: 401 sem token ou com token inválido.

    JWKS fora do ar é 503: é falha passageira, e o app não deve tirar a pessoa da conta.
    """
    tipo, _, token = (authorization or "").partition(" ")
    if tipo.lower() != "bearer" or not token:
        raise HTTPException(401, "Entre na sua conta para continuar",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        return validar(token.strip())
    except ChavesIndisponiveis:
        raise HTTPException(503, "Não deu para confirmar sua conta agora. Tente de novo em instantes.") from None
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Sua sessão expirou. Entre de novo.",
                            headers={"WWW-Authenticate": "Bearer"}) from None
