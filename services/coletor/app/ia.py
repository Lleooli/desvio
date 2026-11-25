"""IA do Desvio no Groq (plano gratuito), com saída em JSON validada por schema.

Os modelos gpt-oss aceitam structured outputs estritos. O plano gratuito tem,
por modelo e por organização, 30 requisições e 8.000 tokens por minuto: o
Limitador segura as chamadas para não tomar 429. Qualquer falha vira
IAIndisponivel, e quem chama usa o plano B sem IA (ver PRD, seção de IA).
"""
from __future__ import annotations

import asyncio
import collections
import hashlib
import json
import os
import re
import time
import unicodedata

import httpx

from . import cache, roteiro, uso_ia

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELO_RACIOCINIO = os.getenv("PV_MODELO_RACIOCINIO", "openai/gpt-oss-120b")
MODELO_RAPIDO = os.getenv("PV_MODELO_RAPIDO", "openai/gpt-oss-20b")


class IAIndisponivel(RuntimeError):
    pass


def estimar_tokens(texto: str) -> int:
    return len(texto) // 4 + 1


class Limitador:
    """Janela deslizante de 60 s com limite de requisições e de tokens.

    `reservar` é a porta de entrada: um lock por limitador (um por modelo) faz as
    chamadas simultâneas entrarem uma de cada vez, e a checagem é refeita depois
    de cada espera, para duas chamadas não ocuparem a mesma vaga.
    """

    def __init__(self, rpm: int = 30, tpm: int = 8000, relogio=time.monotonic, dormir=asyncio.sleep):
        self.rpm, self.tpm, self.relogio, self.dormir = rpm, tpm, relogio, dormir
        self._uso: collections.deque[tuple[float, int]] = collections.deque()
        self._trava = asyncio.Lock()

    def _limpar(self, agora: float) -> None:
        while self._uso and agora - self._uso[0][0] >= 60:
            self._uso.popleft()

    def espera(self, tokens: int) -> float:
        if tokens > self.tpm:
            return float("inf")  # nunca cabe: quem chama cai no plano B
        agora = self.relogio()
        self._limpar(agora)
        usados = sum(t for _, t in self._uso)
        if len(self._uso) < self.rpm and usados + tokens <= self.tpm:
            return 0.0
        return max(0.0, 60 - (agora - self._uso[0][0]))

    def registrar(self, tokens: int) -> None:
        self._uso.append((self.relogio(), tokens))

    async def reservar(self, tokens: int, prazo_s: float) -> None:
        """Espera a vez e registra o uso; IAIndisponivel se a vaga só abrir depois do prazo."""
        inicio = self.relogio()
        async with self._trava:
            while True:
                espera = self.espera(tokens)
                if espera == 0:
                    self.registrar(tokens)
                    return
                if self.relogio() - inicio + espera > prazo_s:
                    raise IAIndisponivel(f"limite do Groq: {espera:.0f}s de espera")
                await self.dormir(espera)


_limitadores: dict[str, Limitador] = {}


async def chamar_json(client: httpx.AsyncClient, *, modelo: str, sistema: str, dados: dict,
                      schema: dict, nome: str, max_tokens: int = 1024, timeout: float = 10.0) -> dict:
    """Chama o Groq. `timeout` é o prazo total: espera no limitador + requisição HTTP."""
    chave = os.getenv("GROQ_API_KEY")
    if not chave:
        raise IAIndisponivel("GROQ_API_KEY não configurada")
    inicio = time.monotonic()
    conteudo = json.dumps(dados, ensure_ascii=False)
    tokens = estimar_tokens(sistema + conteudo) + max_tokens
    lim = _limitadores.setdefault(modelo, Limitador())
    try:
        await asyncio.wait_for(lim.reservar(tokens, timeout), timeout)
    except TimeoutError as e:
        raise IAIndisponivel(f"limite do Groq: fila de {modelo} passou do prazo de {timeout:g}s") from e
    except RuntimeError as e:  # lock preso a outro event loop (vários asyncio.run): plano B, não 500
        raise IAIndisponivel(f"limite do Groq indisponível: {e}") from e
    restante = timeout - (time.monotonic() - inicio)
    if restante <= 0:
        raise IAIndisponivel(f"Groq: prazo de {timeout:g}s esgotado na fila")
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
        r = await asyncio.wait_for(client.post(GROQ_URL, json=corpo, timeout=restante,
                                               headers={"Authorization": f"Bearer {chave}"}), restante)
    except TimeoutError as e:
        raise IAIndisponivel(f"Groq passou do prazo de {timeout:g}s") from e
    except httpx.HTTPError as e:
        raise IAIndisponivel(f"Groq não respondeu: {e.__class__.__name__}") from e
    if r.status_code == 429:
        raise IAIndisponivel(f"Groq 429, tente em {r.headers.get('retry-after', '?')}s")
    if r.status_code >= 400:
        raise IAIndisponivel(f"Groq {r.status_code}")
    try:
        usados = int((r.json().get("usage") or {}).get("total_tokens") or tokens)
    except (TypeError, ValueError, AttributeError):
        usados = tokens
    # conta na cota do dia, mesmo se a saída vier ruim; numa thread e sem esperar, para
    # o banco lento nunca empurrar a resposta da IA para além do prazo
    asyncio.get_running_loop().run_in_executor(None, uso_ia.registrar, modelo, usados)
    try:
        saida = json.loads(r.json()["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise IAIndisponivel("Groq devolveu JSON inválido") from e
    if not isinstance(saida, dict) or any(k not in saida for k in schema.get("required", [])):
        raise IAIndisponivel("Groq devolveu JSON fora do schema")
    return saida


# --- Triagem -----------------------------------------------------------------

MAX_PERGUNTAS = 5
# `multi`: a pessoa pode marcar mais de uma opção; sem ele, um toque responde
PRIMEIRA_PERGUNTA = {"pergunta": "O que não pode faltar numa viagem sua?",
                     "opcoes": ["Comida boa", "Natureza", "Pontos turísticos", "Descanso", "Aventura"],
                     "multi": True}
PERGUNTAS_RESERVA = [
    {"pergunta": "Com quem você costuma viajar?", "opcoes": ["Sozinho", "Casal", "Família com crianças", "Amigos", "Com pet"], "multi": False},
    {"pergunta": "Que comida você procura na estrada?", "opcoes": ["Comida caseira", "Churrasco", "Lanche rápido", "Vegetariana", "Tanto faz"],
     "multi": True},
    {"pergunta": "Quanto quer gastar por refeição?", "opcoes": ["Até R$ 50", "R$ 50 a 100", "Mais de R$ 100"], "multi": False},
    {"pergunta": "Prefere lugares famosos ou escondidos?", "opcoes": ["Famosos", "Escondidos", "Um pouco de cada"], "multi": False},
]
# assunto de cada pergunta de reserva, reconhecido pelo começo das palavras da pergunta (sem acento);
# "pet" só como palavra inteira, para "petisco" e "repetir" não contarem
_ASSUNTOS_RESERVA = [
    ("companhia", ("com quem", "acompanh", "companhia", "sozinh", "familia", r"pets?\b")),
    ("comida", ("comida", "comer", "culinaria", "gastronom", "restaurante", "prato")),
    ("orcamento", ("gastar", "gasto", "orcamento", "preco", r"r\$", "custo")),
    ("fama", ("famos", "escondid", "conhecid", "fora do roteiro", "alternativ")),
]


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def _assuntos(perguntas: list[str]) -> set[str]:
    textos = [_sem_acento(p) for p in perguntas]
    return {nome for nome, chaves in _ASSUNTOS_RESERVA
            if any(re.search(r"(?<!\w)" + k, t) for t in textos for k in chaves)}


def resumo_simples(respostas: list[dict]) -> str | None:
    """Resumo sem IA: as respostas da triagem em uma linha, para o ranqueamento usar."""
    partes = [f'{str(r.get("pergunta") or "").rstrip(" ?")}: {r.get("resposta")}'
              for r in respostas if r.get("resposta")]
    return ". ".join(partes) + "." if partes else None


def _proxima_reserva(respostas: list[dict]) -> dict | None:
    ja = _assuntos([str(r.get("pergunta") or "") for r in respostas])
    for (nome, _), p in zip(_ASSUNTOS_RESERVA, PERGUNTAS_RESERVA):
        if nome not in ja:
            return p
    return None
_SCHEMA_TRIAGEM = {
    "type": "object", "additionalProperties": False,
    "required": ["pergunta", "opcoes", "multi", "fim", "resumo"],
    "properties": {"pergunta": {"type": ["string", "null"]},
                   "opcoes": {"type": "array", "items": {"type": "string"}},
                   "multi": {"type": "boolean"},
                   "fim": {"type": "boolean"},
                   "resumo": {"type": ["string", "null"]}},
}
_SISTEMA_TRIAGEM = (
    "Você monta o perfil de gosto de viagem de uma pessoa no Brasil, com no máximo "
    f"{MAX_PERGUNTAS} perguntas. Recebe as respostas até agora. Faça a próxima pergunta curta, "
    "tratando por 'você', com 2 a 5 opções curtas, sem repetir assunto; multi=true quando fizer "
    "sentido marcar mais de uma opção. Com restantes=1, a pergunta é aberta: a pessoa responde por "
    "escrito e as opções são só sugestões. Quando já der para "
    "recomendar lugares (ou na última pergunta), responda fim=true, pergunta=null, opcoes=[] e "
    "um resumo de uma frase do gosto da pessoa. Português do Brasil.")


async def triagem(client: httpx.AsyncClient, respostas: list[dict]) -> dict:
    if not respostas:
        return {**PRIMEIRA_PERGUNTA, "fim": False, "resumo": None, "fonte": "fixa", "livre": False}
    try:
        r = await chamar_json(client, modelo=MODELO_RACIOCINIO, sistema=_SISTEMA_TRIAGEM,
                              dados={"respostas": respostas, "restantes": MAX_PERGUNTAS - len(respostas)},
                              schema=_SCHEMA_TRIAGEM, nome="triagem", max_tokens=400)
        r["fonte"] = "ia"
    except IAIndisponivel:
        p = _proxima_reserva(respostas)
        r = ({**p, "fim": False, "resumo": None} if p
             else {"pergunta": None, "opcoes": [], "fim": True, "resumo": None})
        r["fonte"] = "fixa"
    # a última pergunta aceita texto livre, venha da IA ou da reserva
    r["livre"] = len(respostas) == MAX_PERGUNTAS - 1
    r["multi"] = bool(r.get("multi"))
    if len(respostas) >= MAX_PERGUNTAS or r["fim"] or not r.get("pergunta"):
        r.update(pergunta=None, opcoes=[], fim=True, multi=False, livre=False)
        r["resumo"] = r.get("resumo") or resumo_simples(respostas)
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


async def _ranquear_pela_ia(client: httpx.AsyncClient, cards: list[dict], resumo: str) -> list[dict] | None:
    """Os cards ordenados pelo Groq, ou None quando a IA não respondeu (plano B de quem chama)."""
    topo, resto = cards[:MAX_RANQUEAR], cards[MAX_RANQUEAR:]
    if not resumo or len(topo) < 2:
        return None
    try:
        r = await chamar_json(client, modelo=MODELO_RAPIDO, sistema=_SISTEMA_RANQUEAR,
                              dados={"gosto": resumo, "cards": [_card_enxuto(c) for c in topo]},
                              schema=_SCHEMA_RANQUEAR, nome="ranqueamento", max_tokens=600)
    except IAIndisponivel:
        return None
    return _reordenar(topo, r["ids"]) + resto


async def ranquear(client: httpx.AsyncClient, cards: list[dict], resumo: str) -> list[dict]:
    """Os cards ordenados pelo gosto; sem IA, na ordem em que vieram."""
    return await _ranquear_pela_ia(client, cards, resumo) or cards


def _norm_cidade(s: str) -> str:
    """Igual a coletor._norm: a chave do cache não muda com acento ou maiúscula."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def chave_ranque(cidade: str, categoria: str, resumo: str) -> str:
    """Cache do ranqueamento: (cidade, categoria, hash do resumo da triagem)."""
    digest = hashlib.sha256(resumo.encode()).hexdigest()
    return f"ranque|{_norm_cidade(cidade)}|{categoria}|{digest}"


def _categorias_do_topo(cards: list[dict]) -> list[str]:
    return list(dict.fromkeys(c.get("categoria") or "" for c in cards))


def _ordem_em_cache(parada: dict, resumo: str, exata: bool = True) -> list | None:
    """A ordem já ranqueada para esta cidade/categoria/resumo, ou None.

    Com `exata`, só vale se o cache tem exatamente estes cards (o worker: card novo vai ao
    Groq). Sem `exata`, vale como prioridade (GET da viagem): depois de um swipe o topo
    muda, e os cards que o cache não conhece vão para o fim, sem perder o ranqueamento.
    """
    topo = (parada.get("cards") or [])[:MAX_RANQUEAR]
    if len(topo) < 2 or not resumo:
        return None
    ids = {c["id"] for c in topo}
    cidade = parada.get("nome") or ""
    for cat in _categorias_do_topo(topo):
        guardado = cache.obter(chave_ranque(cidade, cat, resumo))
        if not isinstance(guardado, list):
            continue
        if exata and len(guardado) == len(ids) and set(guardado) == ids:
            return guardado
        if not exata and len(ids & set(guardado)) >= 2:
            return guardado
    return None


def reaplicar_cache(paradas: list[dict], resumo: str | None) -> None:
    """Reordena pelo cache, sem chamar o Groq. Sem resumo ou sem cache, a ordem fica como está."""
    if not resumo:
        return
    for parada in paradas:
        ordem = _ordem_em_cache(parada, resumo, exata=False)
        if not ordem:
            continue
        topo, resto = parada["cards"][:MAX_RANQUEAR], parada["cards"][MAX_RANQUEAR:]
        parada["cards"] = _reordenar(topo, ordem) + resto


async def ranquear_paradas(paradas: list[dict], resumo: str | None) -> None:
    """Ranqueia os 30 primeiros cards de cada parada com o resumo da triagem.

    A ordem de quem chamou (a estatística) vale para o resto e para o plano B.
    Sem resumo, não chama a IA. Cidade e categoria já ranqueadas com o mesmo
    resumo saem do cache e não vão ao Groq de novo.
    """
    if not resumo:
        return
    async with httpx.AsyncClient() as client:
        for parada in paradas:
            cards = parada.get("cards") or []
            topo, resto = cards[:MAX_RANQUEAR], cards[MAX_RANQUEAR:]
            if len(topo) < 2:
                continue
            ordem = _ordem_em_cache(parada, resumo)
            if ordem:
                parada["cards"] = _reordenar(topo, ordem) + resto
                continue
            ordenados = await _ranquear_pela_ia(client, topo, resumo)
            if ordenados is None:
                continue  # plano B: fica a ordem estatística, e nada vai ao cache como se fosse da IA
            ordem = [c["id"] for c in ordenados]
            cidade = parada.get("nome") or ""
            for cat in _categorias_do_topo(topo):
                cache.guardar(chave_ranque(cidade, cat, resumo), ordem)
            parada["cards"] = ordenados + resto


# --- Roteiro -----------------------------------------------------------------

_SCHEMA_ROTEIRO = {
    "type": "object", "additionalProperties": False, "required": ["ordem"],
    "properties": {"ordem": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["id", "porque"],
        "properties": {"id": {"type": "string"}, "porque": {"type": "string"}}}}},
}
_SISTEMA_ROTEIRO = (
    "Você ajusta a ordem das paradas de uma viagem por terra (carro, moto ou bicicleta; o veículo vem no contexto). Recebe os lugares já em ordem de km "
    "e o contexto (hora de saída, dias). Quando houver, `chegada` (HH:MM) e `dia` dizem quando a "
    "pessoa passa por cada lugar. Ajuste ao horário: se houver restaurante, o almoço é um com "
    "chegada entre 11h e 14h; mirante no fim da tarde, pernoite. Não volte na estrada mais de 30 km. "
    "Para cada lugar, uma linha curta dizendo por quê, em português do Brasil.")


def _chegada(saida: str | None, horas: float | None) -> dict:
    """`chegada` (HH:MM) e `dia` (1 é o dia da saída) de um lugar; vazio sem saída ou sem horas."""
    # o POST /roteiro aceita contexto livre: saída fora de HH:MM só fica sem chegada
    hora = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", saida) if isinstance(saida, str) else None
    if not hora or not isinstance(horas, (int, float)):
        return {}
    total = int(hora[1]) * 60 + int(hora[2]) + round(horas * 60)
    dia, minutos = divmod(total, 24 * 60)
    return {"chegada": f"{minutos // 60:02d}:{minutos % 60:02d}", "dia": dia + 1}


async def ajustar_roteiro(client: httpx.AsyncClient, itens: list[dict], contexto: dict) -> dict:
    base = roteiro.ordenar_na_rota(itens)
    saida = contexto.get("saida")
    try:
        r = await chamar_json(client, modelo=MODELO_RACIOCINIO, sistema=_SISTEMA_ROTEIRO,
                              dados={"contexto": contexto,
                                     "lugares": [{**_card_enxuto(c), "km_na_rota": c.get("km_na_rota"),
                                                  "horas_desde_saida": c.get("horas_desde_saida"),
                                                  **_chegada(saida, c.get("horas_desde_saida")),
                                                  "horarios": c.get("horarios")} for c in base]},
                              schema=_SCHEMA_ROTEIRO, nome="roteiro", max_tokens=1200)
    except IAIndisponivel:
        return {"itens": base, "explicacoes": {}, "fonte": "geometria"}
    validos = {c["id"] for c in base}
    ordem = [o for o in r["ordem"] if isinstance(o, dict) and o.get("id") in validos]
    explic = {o["id"]: str(o.get("porque", "")) for o in ordem}
    return {"itens": _reordenar(base, [o["id"] for o in ordem]), "explicacoes": explic, "fonte": "ia"}
