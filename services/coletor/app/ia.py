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
                      schema: dict, nome: str, max_tokens: int = 1024, timeout: float = 10.0,
                      espera_max: float | None = None) -> dict:
    """Chama o Groq. `timeout` é o prazo total: espera no limitador + requisição HTTP.

    Com `espera_max` (só no worker, onde ninguém espera na tela), a fila do limitador
    pode esperar até `espera_max` segundos, e `timeout` vale só para a requisição HTTP.
    """
    chave = os.getenv("GROQ_API_KEY")
    if not chave:
        raise IAIndisponivel("GROQ_API_KEY não configurada")
    inicio = time.monotonic()
    conteudo = json.dumps(dados, ensure_ascii=False)
    tokens = estimar_tokens(sistema + conteudo) + max_tokens
    lim = _limitadores.setdefault(modelo, Limitador())
    prazo_fila = timeout if espera_max is None else espera_max
    try:
        await asyncio.wait_for(lim.reservar(tokens, prazo_fila), prazo_fila)
    except TimeoutError as e:
        raise IAIndisponivel(f"limite do Groq: fila de {modelo} passou do prazo de {prazo_fila:g}s") from e
    except RuntimeError as e:  # lock preso a outro event loop (vários asyncio.run): plano B, não 500
        raise IAIndisponivel(f"limite do Groq indisponível: {e}") from e
    restante = timeout - (time.monotonic() - inicio) if espera_max is None else timeout
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


# Ranqueamento no worker (issue #95): uma parada por chamada esgotava os 8 mil tokens por
# minuto na sétima parada e o resto caía no plano B. Agora as paradas vão juntas, até
# LOTE_TOKENS de entrada por chamada, com os cards numerados (número gasta menos token que
# o id), e a fila do limitador espera até ESPERA_LOTE_S pela vaga em vez de desistir em 10 s.
LOTE_TOKENS = int(os.getenv("PV_RANQUE_LOTE_TOKENS", "3000"))
ESPERA_LOTE_S = float(os.getenv("PV_RANQUE_ESPERA_S", "70"))
_SCHEMA_RANQUEAR_LOTE = {
    "type": "object", "additionalProperties": False, "required": ["paradas"],
    "properties": {"paradas": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["parada", "ordem"],
        "properties": {"parada": {"type": "integer"},
                       "ordem": {"type": "array", "items": {"type": "integer"}}}}}},
}
_SISTEMA_RANQUEAR_LOTE = (
    "Você ordena lugares de várias paradas de uma viagem pelo gosto da pessoa. Recebe o resumo do "
    "gosto e, para cada parada, os cards numerados (n). Para cada parada, devolva todos os n dela, "
    "do mais recomendado ao menos, sem inventar números.")


def _parada_do_lote(i: int, topo: list[dict]) -> dict:
    # sem o id (vai o número), sem campo vazio e com descrição curta: cada token conta no
    # limite por minuto, e 12 paradas de 15 cards já passam dele
    cards = [{"n": n, **{k: v for k, v in {**_card_enxuto(c), "descricao": (c.get("descricao") or "")[:60],
                                            "sobre": (c.get("sobre") or [])[:3]}.items()
                         if k != "id" and v not in (None, "", [])}}
             for n, c in enumerate(topo)]
    return {"parada": i, "cards": cards}


def _lotes(topos: list[list[dict]]) -> list[list[int]]:
    """Índices das paradas agrupados para caber em LOTE_TOKENS de entrada por chamada."""
    lotes: list[list[int]] = []
    soma = 0
    for i, topo in enumerate(topos):
        t = estimar_tokens(json.dumps(_parada_do_lote(i, topo), ensure_ascii=False))
        if lotes and soma + t <= LOTE_TOKENS:
            lotes[-1].append(i)
            soma += t
        else:
            lotes.append([i])
            soma = t
    return lotes


async def _ranquear_lote_pela_ia(client: httpx.AsyncClient, topos: list[list[dict]],
                                 resumo: str) -> list[list[dict] | None]:
    """Os cards de cada parada ordenados pelo Groq, em poucas chamadas; None na parada sem resposta."""
    saida: list[list[dict] | None] = [None] * len(topos)
    for lote in _lotes(topos):
        n_cards = sum(len(topos[i]) for i in lote)
        try:
            r = await chamar_json(client, modelo=MODELO_RAPIDO, sistema=_SISTEMA_RANQUEAR_LOTE,
                                  dados={"gosto": resumo, "paradas": [_parada_do_lote(i, topos[i]) for i in lote]},
                                  schema=_SCHEMA_RANQUEAR_LOTE, nome="ranqueamento",
                                  max_tokens=min(2000, 300 + 8 * n_cards), espera_max=ESPERA_LOTE_S)
        except IAIndisponivel:
            continue  # plano B deste lote; o próximo ainda tenta
        for p in r["paradas"]:
            i = p.get("parada") if isinstance(p, dict) else None
            if i not in lote or saida[i] is not None:
                continue
            ids = [topos[i][n]["id"] for n in p.get("ordem") or []
                   if isinstance(n, int) and 0 <= n < len(topos[i])]
            if ids:
                saida[i] = _reordenar(topos[i], ids)
    return saida


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
    resumo saem do cache e não vão ao Groq de novo. As outras vão juntas, em lotes
    (_ranquear_lote_pela_ia); o lote que falha fica com a ordem estatística.
    """
    if not resumo:
        return
    pendentes = []
    for parada in paradas:
        cards = parada.get("cards") or []
        topo, resto = cards[:MAX_RANQUEAR], cards[MAX_RANQUEAR:]
        if len(topo) < 2:
            continue
        ordem = _ordem_em_cache(parada, resumo)
        if ordem:
            parada["cards"] = _reordenar(topo, ordem) + resto
        else:
            pendentes.append(parada)
    if not pendentes:
        return
    topos = [p["cards"][:MAX_RANQUEAR] for p in pendentes]
    async with httpx.AsyncClient() as client:
        respostas = await _ranquear_lote_pela_ia(client, topos, resumo)
    for parada, topo, ordenados in zip(pendentes, topos, respostas):
        if ordenados is None:
            continue  # plano B: fica a ordem estatística, e nada vai ao cache como se fosse da IA
        ordem = [c["id"] for c in ordenados]
        cidade = parada.get("nome") or ""
        for cat in _categorias_do_topo(topo):
            cache.guardar(chave_ranque(cidade, cat, resumo), ordem)
        parada["cards"] = ordenados + parada["cards"][MAX_RANQUEAR:]


# --- Roteiro -----------------------------------------------------------------

_SCHEMA_ROTEIRO = {
    "type": "object", "additionalProperties": False, "required": ["ordem"],
    "properties": {"ordem": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["id", "porque"],
        "properties": {"id": {"type": "string"}, "porque": {"type": "string"}}}}},
}
_SISTEMA_ROTEIRO = (
    "Você ajusta a ordem das paradas de uma viagem por terra (carro, moto ou bicicleta). Recebe o "
    "contexto e os lugares já em ordem de km, com a agenda que o servidor calculou para essa ordem: "
    "`dia`, `chegada` (HH:MM), `pernoite` (true: a pessoa dorme na cidade desse lugar) e "
    "`aberto_na_chegada` (false: fechado nessa hora; null: horário desconhecido). Cada dia tem no "
    "máximo `horas_volante_por_dia` horas de estrada e ninguém chega a um lugar depois das 22h; o "
    "servidor refaz a agenda com a ordem que você devolver. Só troque lugares vizinhos, sem voltar "
    "na estrada mais de 30 km, para encaixar o almoço (chegada entre 11h e 15h), o jantar (entre 18h "
    "e 22h) e o mirante no fim da tarde. Use a `chegada` de cada lugar: não chame de almoço ou jantar "
    "um lugar fora dessas horas, não fale em madrugada e, quando aberto_na_chegada for false, diga "
    "que o lugar estará fechado em vez de recomendar a visita. Para cada lugar, uma linha curta "
    "dizendo por quê, em português do Brasil, tratando por 'você'.")

# Palavras da explicação que só valem com a chegada dentro da janela (minutos do dia)
_JANELAS = (
    (("almoco", "almocar", "almoca"), 11 * 60, 15 * 60),
    (("jantar", "janta"), 18 * 60, 23 * 60),
    (("cafe da manha",), 5 * 60, 10 * 60 + 30),
    (("por do sol", "fim da tarde", "entardecer"), 16 * 60, 19 * 60 + 30),
)
VOLTA_MAXIMA_KM = 30


def _coerente(porque: str, item: dict) -> bool:
    """Se a explicação da IA bate com a agenda do lugar (hora de chegada e horário de funcionamento)."""
    texto = _sem_acento(porque)
    if "madrugada" in texto:
        return False  # a agenda nunca chega a um lugar de madrugada
    chegada = roteiro.minutos(item.get("chegada"))
    if chegada is None:
        return True
    for palavras, ini, fim in _JANELAS:
        if any(p in texto for p in palavras) and not ini <= chegada <= fim:
            return False
    return not (item.get("aberto_na_chegada") is False and "fechad" not in texto)


def _porque_da_agenda(item: dict) -> str | None:
    """Explicação sem IA, só com o que a agenda sabe; None quando não há nada a dizer."""
    partes = []
    if item.get("aberto_na_chegada") is False:
        partes.append(f'Você chega às {item["chegada"]}, e nessa hora deve estar fechado. Confira o horário.')
    if item.get("pernoite"):
        partes.append(f'Pernoite do dia {item["dia"]} nesta cidade.')
    return " ".join(partes) or None


def _volta_na_estrada(itens: list[dict]) -> bool:
    """Se a ordem volta mais de VOLTA_MAXIMA_KM em relação ao ponto mais longe já alcançado."""
    mais_longe = 0.0
    for c in itens:
        km = c.get("km_na_rota") or 0
        if km < mais_longe - VOLTA_MAXIMA_KM:
            return True
        mais_longe = max(mais_longe, km)
    return False


def _plano_b(base: list[dict]) -> dict:
    return {"itens": base, "explicacoes": {c["id"]: p for c in base if (p := _porque_da_agenda(c))},
            "fonte": "geometria"}


async def ajustar_roteiro(client: httpx.AsyncClient, itens: list[dict], contexto: dict,
                          veiculo: str | None = None) -> dict:
    """A ordem de visita com dias, chegada e pernoite; a IA ajusta a ordem e explica cada lugar.

    A agenda (roteiro.agendar) é sem IA: dias com limite de horas ao volante, pernoite e
    hora de chegada. A resposta da IA é conferida (issue #95): ordem que volta mais de
    30 km na estrada vira a ordem do km; explicação que não bate com a chegada ou com o
    horário de funcionamento (jantar de manhã, refeição em lugar fechado, madrugada) é
    trocada pela da agenda. Sem IA, fica a ordem do km com a agenda (`fonte` "geometria").
    """
    veiculo = veiculo or contexto.get("veiculo") or "carro"
    saida, data = contexto.get("saida"), contexto.get("data")
    base = roteiro.agendar(roteiro.ordenar_na_rota(itens), saida, veiculo, data)
    try:
        r = await chamar_json(client, modelo=MODELO_RACIOCINIO, sistema=_SISTEMA_ROTEIRO,
                              dados={"contexto": contexto,
                                     "horas_volante_por_dia": roteiro.HORAS_VOLANTE.get(veiculo, 9),
                                     "lugares": [{**_card_enxuto(c), "km_na_rota": c.get("km_na_rota"),
                                                  "horas_desde_saida": c.get("horas_desde_saida"),
                                                  **{k: c[k] for k in ("dia", "chegada", "pernoite",
                                                                       "aberto_na_chegada") if k in c},
                                                  "horarios": c.get("horarios")} for c in base]},
                              schema=_SCHEMA_ROTEIRO, nome="roteiro", max_tokens=1200)
    except IAIndisponivel:
        return _plano_b(base)
    validos = {c["id"] for c in base}
    ordem = [o for o in r["ordem"] if isinstance(o, dict) and o.get("id") in validos]
    itens_ia = roteiro.agendar(_reordenar(base, [o["id"] for o in ordem]), saida, veiculo, data)
    if _volta_na_estrada(itens_ia):
        itens_ia = base  # a IA mandou voltar na estrada: vale a ordem do km
    por_id = {c["id"]: c for c in itens_ia}
    explic = {}
    for o in ordem:
        item, porque = por_id[o["id"]], str(o.get("porque", "")).strip()
        if porque and _coerente(porque, item):
            explic[o["id"]] = porque
        elif p := _porque_da_agenda(item):
            explic[o["id"]] = p
    for c in itens_ia:  # o que a IA não explicou e a agenda tem a dizer (fechado, pernoite)
        if c["id"] not in explic and (p := _porque_da_agenda(c)):
            explic[c["id"]] = p
    return {"itens": itens_ia, "explicacoes": explic, "fonte": "ia"}
