"""IA do Desvio no Groq (plano gratuito), com saída em JSON validada por schema.

Os modelos gpt-oss aceitam structured outputs estritos. O plano gratuito tem,
por modelo e por organização, 30 requisições e 8.000 tokens por minuto: o
Limitador segura as chamadas para não tomar 429. Qualquer falha vira
IAIndisponivel, e quem chama usa o plano B sem IA (ver PRD, seção de IA).
"""
from __future__ import annotations

import asyncio
import collections
import json
import os
import time

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELO_RACIOCINIO = os.getenv("PV_MODELO_RACIOCINIO", "openai/gpt-oss-120b")
MODELO_RAPIDO = os.getenv("PV_MODELO_RAPIDO", "openai/gpt-oss-20b")


class IAIndisponivel(RuntimeError):
    pass


def estimar_tokens(texto: str) -> int:
    return len(texto) // 4 + 1


class Limitador:
    """Janela deslizante de 60 s com limite de requisições e de tokens."""

    def __init__(self, rpm: int = 30, tpm: int = 8000, relogio=time.monotonic):
        self.rpm, self.tpm, self.relogio = rpm, tpm, relogio
        self._uso: collections.deque[tuple[float, int]] = collections.deque()

    def _limpar(self, agora: float) -> None:
        while self._uso and agora - self._uso[0][0] >= 60:
            self._uso.popleft()

    def espera(self, tokens: int) -> float:
        agora = self.relogio()
        self._limpar(agora)
        usados = sum(t for _, t in self._uso)
        if len(self._uso) < self.rpm and usados + tokens <= self.tpm:
            return 0.0
        return max(0.0, 60 - (agora - self._uso[0][0]))

    def registrar(self, tokens: int) -> None:
        self._uso.append((self.relogio(), tokens))


_limitadores: dict[str, Limitador] = {}


async def chamar_json(client: httpx.AsyncClient, *, modelo: str, sistema: str, dados: dict,
                      schema: dict, nome: str, max_tokens: int = 1024, timeout: float = 10.0) -> dict:
    chave = os.getenv("GROQ_API_KEY")
    if not chave:
        raise IAIndisponivel("GROQ_API_KEY não configurada")
    conteudo = json.dumps(dados, ensure_ascii=False)
    tokens = estimar_tokens(sistema + conteudo) + max_tokens
    lim = _limitadores.setdefault(modelo, Limitador())
    espera = lim.espera(tokens)
    if espera > timeout:
        raise IAIndisponivel(f"limite do Groq: {espera:.0f}s de espera para {modelo}")
    if espera:
        await asyncio.sleep(espera)
    lim.registrar(tokens)
    corpo = {
        "model": modelo,
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": conteudo}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": nome, "schema": schema, "strict": True}},
        "reasoning_effort": "low",  # tokens de raciocínio contam no limite por minuto
        "max_completion_tokens": max_tokens,
        "temperature": 0.3,
    }
    try:
        r = await client.post(GROQ_URL, json=corpo, timeout=timeout,
                              headers={"Authorization": f"Bearer {chave}"})
    except httpx.HTTPError as e:
        raise IAIndisponivel(f"Groq não respondeu: {e.__class__.__name__}") from e
    if r.status_code == 429:
        raise IAIndisponivel(f"Groq 429, tente em {r.headers.get('retry-after', '?')}s")
    if r.status_code >= 400:
        raise IAIndisponivel(f"Groq {r.status_code}")
    try:
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise IAIndisponivel("Groq devolveu JSON inválido") from e
