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

from . import roteiro

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


# --- Triagem -----------------------------------------------------------------

MAX_PERGUNTAS = 5
PRIMEIRA_PERGUNTA = {"pergunta": "O que não pode faltar numa viagem sua?",
                     "opcoes": ["Comida boa", "Natureza", "Pontos turísticos", "Descanso", "Aventura"]}
PERGUNTAS_RESERVA = [
    {"pergunta": "Com quem você costuma viajar?", "opcoes": ["Sozinho", "Casal", "Família com crianças", "Amigos", "Com pet"]},
    {"pergunta": "Que comida você procura na estrada?", "opcoes": ["Comida caseira", "Churrasco", "Lanche rápido", "Vegetariana", "Tanto faz"]},
    {"pergunta": "Quanto quer gastar por refeição?", "opcoes": ["Até R$ 50", "R$ 50 a 100", "Mais de R$ 100"]},
    {"pergunta": "Prefere lugares famosos ou escondidos?", "opcoes": ["Famosos", "Escondidos", "Um pouco de cada"]},
]
_SCHEMA_TRIAGEM = {
    "type": "object", "additionalProperties": False,
    "required": ["pergunta", "opcoes", "fim", "resumo"],
    "properties": {"pergunta": {"type": ["string", "null"]},
                   "opcoes": {"type": "array", "items": {"type": "string"}},
                   "fim": {"type": "boolean"},
                   "resumo": {"type": ["string", "null"]}},
}
_SISTEMA_TRIAGEM = (
    "Você monta o perfil de gosto de viagem de uma pessoa no Brasil, com no máximo "
    f"{MAX_PERGUNTAS} perguntas. Recebe as respostas até agora. Faça a próxima pergunta curta, "
    "tratando por 'você', com 2 a 5 opções curtas, sem repetir assunto. Quando já der para "
    "recomendar lugares (ou na última pergunta), responda fim=true, pergunta=null, opcoes=[] e "
    "um resumo de uma frase do gosto da pessoa. Português do Brasil.")


async def triagem(client: httpx.AsyncClient, respostas: list[dict]) -> dict:
    if not respostas:
        return {**PRIMEIRA_PERGUNTA, "fim": False, "resumo": None, "fonte": "fixa"}
    try:
        r = await chamar_json(client, modelo=MODELO_RACIOCINIO, sistema=_SISTEMA_TRIAGEM,
                              dados={"respostas": respostas, "restantes": MAX_PERGUNTAS - len(respostas)},
                              schema=_SCHEMA_TRIAGEM, nome="triagem", max_tokens=400)
        r["fonte"] = "ia"
    except IAIndisponivel:
        i = len(respostas) - 1
        r = ({**PERGUNTAS_RESERVA[i], "fim": False, "resumo": None} if i < len(PERGUNTAS_RESERVA)
             else {"pergunta": None, "opcoes": [], "fim": True, "resumo": None})
        r["fonte"] = "fixa"
    if len(respostas) >= MAX_PERGUNTAS or r["fim"]:
        r.update(pergunta=None, opcoes=[], fim=True)
    return r


# --- Ranqueamento ------------------------------------------------------------

MAX_RANQUEAR = 30
_SCHEMA_RANQUEAR = {"type": "object", "additionalProperties": False, "required": ["ids"],
                    "properties": {"ids": {"type": "array", "items": {"type": "string"}}}}
_SISTEMA_RANQUEAR = (
    "Você ordena lugares numa parada de viagem pelo gosto da pessoa. Recebe o resumo do gosto e "
    "os cards. Devolva todos os ids, do mais recomendado ao menos, sem inventar ids.")


def _card_enxuto(c: dict) -> dict:
    return {"id": c["id"], "nome": c.get("nome"), "categoria": c.get("categoria"), "tipo": c.get("tipo"),
            "nota": c.get("nota"), "avaliacoes": c.get("avaliacoes"),
            "descricao": (c.get("descricao") or "")[:120], "sobre": (c.get("sobre") or [])[:5]}


def _reordenar(cards: list[dict], ids: list[str]) -> list[dict]:
    por_id = {c["id"]: c for c in cards}
    vistos: set[str] = set()
    saida = []
    for i in ids:
        if i in por_id and i not in vistos:
            saida.append(por_id[i])
            vistos.add(i)
    return saida + [c for c in cards if c["id"] not in vistos]


async def ranquear(client: httpx.AsyncClient, cards: list[dict], resumo: str) -> list[dict]:
    topo, resto = cards[:MAX_RANQUEAR], cards[MAX_RANQUEAR:]
    if not resumo or len(topo) < 2:
        return cards
    try:
        r = await chamar_json(client, modelo=MODELO_RAPIDO, sistema=_SISTEMA_RANQUEAR,
                              dados={"gosto": resumo, "cards": [_card_enxuto(c) for c in topo]},
                              schema=_SCHEMA_RANQUEAR, nome="ranqueamento", max_tokens=600)
    except IAIndisponivel:
        return cards
    return _reordenar(topo, r["ids"]) + resto


# --- Roteiro -----------------------------------------------------------------

_SCHEMA_ROTEIRO = {
    "type": "object", "additionalProperties": False, "required": ["ordem"],
    "properties": {"ordem": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["id", "porque"],
        "properties": {"id": {"type": "string"}, "porque": {"type": "string"}}}}},
}
_SISTEMA_ROTEIRO = (
    "Você ajusta a ordem das paradas de uma viagem de carro. Recebe os lugares já em ordem de km "
    "e o contexto (hora de saída, dias). Ajuste ao horário: almoço entre 11h e 14h, mirante no fim "
    "da tarde, pernoite. Não volte na estrada mais de 30 km. Para cada lugar, uma linha curta "
    "dizendo por quê, em português do Brasil.")


async def ajustar_roteiro(client: httpx.AsyncClient, itens: list[dict], contexto: dict) -> dict:
    base = roteiro.ordenar_carro(itens)
    try:
        r = await chamar_json(client, modelo=MODELO_RACIOCINIO, sistema=_SISTEMA_ROTEIRO,
                              dados={"contexto": contexto,
                                     "lugares": [{**_card_enxuto(c), "km_na_rota": c.get("km_na_rota"),
                                                  "horarios": c.get("horarios")} for c in base]},
                              schema=_SCHEMA_ROTEIRO, nome="roteiro", max_tokens=1200)
    except IAIndisponivel:
        return {"itens": base, "explicacoes": {}, "fonte": "geometria"}
    validos = {c["id"] for c in base}
    explic = {o["id"]: o["porque"] for o in r["ordem"] if o["id"] in validos}
    return {"itens": _reordenar(base, [o["id"] for o in r["ordem"]]), "explicacoes": explic, "fonte": "ia"}
