"""Erros no Sentry e duração de cada etapa da busca (issue #42).

`sentry-sdk` é a biblioteca oficial: `before_send`, `release`, `environment` e
`send_default_pii` não dá para reproduzir com segurança só com httpx. Sem
`SENTRY_DSN`, nada é inicializado e nenhum byte sai da máquina (testes e dev).

O que vai para o Sentry ou para o log estruturado não leva e-mail, nome, token,
cabeçalho Authorization, cookie nem coordenada. O log de etapa tem `job_id`,
`viagem_id`, `etapa`, `status` e `duracao_ms`.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager

log = logging.getLogger("desvio.observabilidade")

RELEASE_PADRAO = "desvio@0.1.0"
_CHAVES_PESSOAIS = {
    "authorization", "cookie", "cookies", "set-cookie", "x-admin-token",
    "email", "e-mail", "username", "ip_address", "name", "nome",
    "token", "access_token", "refresh_token", "password", "senha",
    "lat", "lon", "latitude", "longitude",
}
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_ativo = False
# Os testes trocam por um transporte que não abre rede.
_transporte = None


def _texto(valor: str) -> str:
    return _BEARER.sub("Bearer [token]", _EMAIL.sub("[e-mail]", valor))


def _limpar(valor):
    if isinstance(valor, str):
        return _texto(valor)
    if isinstance(valor, dict):
        return {k: _limpar(v) for k, v in valor.items() if str(k).lower() not in _CHAVES_PESSOAIS}
    if isinstance(valor, list):
        return [_limpar(v) for v in valor]
    return valor


def antes_de_enviar(evento: dict, hint: dict) -> dict:
    """Tira dado pessoal do evento antes de ele sair para o Sentry."""
    limpo = _limpar(evento)
    if isinstance(limpo, dict):
        limpo.pop("user", None)
        req = limpo.get("request")
        if isinstance(req, dict):
            req.pop("data", None)  # o corpo pode trazer e-mail, origem ou token
            req.pop("cookies", None)
            req.pop("env", None)
    return limpo


def iniciar() -> None:
    """Liga o Sentry se houver DSN. Sem DSN, o processo segue igual."""
    global _ativo
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        _ativo = False
        return
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    opcoes = dict(
        dsn=dsn,
        environment=os.getenv("PV_AMBIENTE") or "desenvolvimento",
        release=os.getenv("PV_RELEASE") or RELEASE_PADRAO,
        send_default_pii=False,
        max_request_body_size="never",
        before_send=antes_de_enviar,
        traces_sample_rate=0,
        integrations=[FastApiIntegration()],
    )
    if _transporte is not None:
        opcoes["transport"] = _transporte
    sentry_sdk.init(**opcoes)
    _ativo = True


def desligar() -> None:
    """Fecha o cliente, para um teste não deixar o envio ligado no seguinte."""
    global _ativo
    _ativo = False
    try:
        import sentry_sdk
        sentry_sdk.init(dsn="")
    except Exception:
        pass


def capturar() -> None:
    """Manda a exceção corrente. Sem Sentry ligado, não faz nada."""
    if not _ativo:
        return
    import sentry_sdk
    sentry_sdk.capture_exception()


def linha(job_id: str | None, etapa: str, status: str, duracao_ms: float | None = None,
          viagem_id: str | None = None) -> None:
    """Uma linha JSON. Só identificadores técnicos e a duração."""
    if not job_id:
        return
    payload: dict = {"evento": "etapa_busca", "job_id": job_id, "etapa": etapa, "status": status}
    if duracao_ms is not None:
        payload["duracao_ms"] = round(duracao_ms)
    if viagem_id:
        payload["viagem_id"] = str(viagem_id)
    log.info("%s", json.dumps(payload, ensure_ascii=False))


class _Relogio:
    def __init__(self, job_id: str | None, etapa: str, viagem_id: str | None):
        self.job_id, self.etapa, self.viagem_id = job_id, etapa, viagem_id
        self.t = time.perf_counter()
        self._fechado = False
        linha(job_id, etapa, "iniciado", viagem_id=viagem_id)

    def _ms(self) -> float:
        return (time.perf_counter() - self.t) * 1000

    def concluir(self) -> None:
        if self._fechado:
            return
        self._fechado = True
        linha(self.job_id, self.etapa, "concluido", self._ms(), self.viagem_id)

    def falha(self) -> None:
        if self._fechado:
            return
        self._fechado = True
        linha(self.job_id, self.etapa, "falha", self._ms(), self.viagem_id)


def relogio(job_id: str | None, etapa: str, viagem_id: str | None = None) -> _Relogio:
    return _Relogio(job_id, etapa, viagem_id)


@contextmanager
def medir(job_id: str | None, etapa: str, viagem_id: str | None = None) -> Iterator[None]:
    """Marca a etapa como iniciada e, ao sair, concluída ou falha, com a duração."""
    marca = relogio(job_id, etapa, viagem_id)
    try:
        yield
    except Exception:
        marca.falha()
        raise
    marca.concluir()
