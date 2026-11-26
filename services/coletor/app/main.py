"""API do planejador. Rode com:  uvicorn app.main:app --reload

Fluxo pensado para o front (estilo Tinder):
1. POST /viagem (carro, moto ou bicicleta)  → job_id e viagem_id (202); a coleta roda no worker
                                              (cidade já coletada há menos de 30 dias sai de parada_cidade;
                                               "forcar": true coleta de novo)
   GET  /jobs/{id}                          → status; quando "pronto", paradas com cards
   GET  /viagens                            → as viagens da pessoa, a mais recente primeiro
   GET  /viagens/{id}                       → paradas e cards ainda não avaliados, pelo gosto
2. POST /swipe (um por card decidido)       → guarda a decisão (bora, passo, favorito)
   DELETE /swipe/{lugar_id}                 → desfaz a decisão e devolve o card à parada
3. POST /roteiro                            → ordem de visita dos aceitos, pelo km na rota
   POST /viagens/{id}/roteiro               → o roteiro da viagem, pelo km ou pela IA, guardado no banco
   PUT  /viagens/{id}/roteiro               → a pessoa reordena ou remove lugares; o Bora continua
4. GET  /perfil                            → resumo do gosto, para a IA
   PATCH /perfil                           → tema, intervalo padrão e resumo da triagem
5. GET  /eu/exportar e DELETE /eu          → LGPD: exportar os dados e apagar a conta
   POST /eu/push-token                     → token do Expo Push, para avisar quando a busca termina
   POST /eu/exportar/link                  → link de download de uso único (10 min) para o app

Toda rota, menos /docs, /fotos e /eu/exportar/arquivo, exige o token do Supabase (Authorization: Bearer);
o usuário sai do token (app/auth.py), nunca do corpo. /fotos não pede token (o
<Image> do app não manda cabeçalho), mas só aceita URLs assinadas pelo coletor.

IA (Groq, com plano B sem IA): POST /triagem, POST /cards/ranquear e
POST /roteiro e POST /viagens/{id}/roteiro com "usar_ia": true.

O Desvio só monta viagens por terra; o modo avião saiu do escopo.
"""
from __future__ import annotations

import os
import secrets
import uuid
from datetime import date

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import banco, cidades, conta, fila, gmaps, ia, metricas, preferencias, push, roteiro, uso_ia, viagens
from .auth import Usuario, usuario_atual

app = FastAPI(title="Planejador de Viagem — coleta de lugares")
# Em produção (PV_AMBIENTE=producao) o CORS fica fechado se PV_CORS_ORIGINS não disser quem pode
_ORIGENS_PADRAO = "" if os.getenv("PV_AMBIENTE") == "producao" else "*"
ORIGENS = [o.strip() for o in os.getenv("PV_CORS_ORIGINS", _ORIGENS_PADRAO).split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ORIGENS, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(banco.ContaApagada)
def _conta_apagada(request: Request, exc: banco.ContaApagada) -> JSONResponse:
    """Token ainda válido de uma conta apagada: 401, como sessão inválida, e não 500."""
    return JSONResponse({"detail": "Essa conta não existe mais. Entre de novo."}, status_code=401,
                        headers={"WWW-Authenticate": "Bearer"})

Categoria = str  # turismo | restaurante | posto | natureza | hospedagem


class Viagem(BaseModel):
    origem: str = Field(examples=["Alegrete, RS"])
    destino: str = Field(examples=["Vitória da Conquista, BA"])
    veiculo: Literal["carro", "moto", "bicicleta"] = "carro"
    intervalo_km: float = Field(ge=10, le=600, examples=[200],
                                description="Distância entre paradas; a pessoa escolhe no app")
    categorias: list[Categoria] = ["turismo", "restaurante", "posto"]
    por_categoria: int = Field(5, ge=1, le=20)
    usar_google_maps: bool = False
    buscar_instagram: bool = True
    saida: str = Field("07:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["07:00"],
                       description="Hora de saída, HH:MM; decide onde cada dia acaba e onde a pessoa dorme")
    data: date | None = Field(None, examples=["2026-12-20"], description="Dia da saída, opcional")
    forcar: bool = Field(False, description="Coleta as cidades de novo, sem usar as já guardadas, para trazer lugares novos")


class Card(BaseModel):
    """Card de lugar como o coletor devolve. Só o id é obrigatório; o resto passa como veio."""
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, examples=["osm:node/123"])
    lat: float | None = Field(None, ge=-90, le=90, allow_inf_nan=False)
    lon: float | None = Field(None, ge=-180, le=180, allow_inf_nan=False)
    km_na_rota: float | None = Field(None, allow_inf_nan=False)


def _dicts(cards: list[Card]) -> list[dict]:
    return [c.model_dump(exclude_unset=True) for c in cards]


class Swipe(BaseModel):
    """Decisão sobre um card. `tipo` é o contrato; `gostou` fica para quem ainda manda bool."""
    card: Card
    tipo: Literal["bora", "passo", "favorito"] | None = None
    gostou: bool | None = None
    viagem: str | None = None
    parada: int | None = Field(None, ge=0, description="Ordem da parada nesta viagem")

    @model_validator(mode="after")
    def completa_tipo(self):
        if self.tipo is None:
            if self.gostou is None:
                raise ValueError("Informe o tipo da decisão: bora, passo ou favorito")
            self.tipo = "bora" if self.gostou else "passo"
        return self


class Roteiro(BaseModel):
    cards: list[Card]
    usar_ia: bool = False
    contexto: dict = {}


class ContextoRoteiro(BaseModel):
    """O que a IA usa para ajustar o roteiro ao horário. Só campos fechados: nada de texto livre no prompt."""
    model_config = ConfigDict(extra="forbid")
    saida: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["07:00"],
                              description="Hora de saída, HH:MM")
    dias: int | None = Field(None, ge=1, le=60, examples=[1], description="Dias de viagem")
    data: date | None = Field(None, examples=["2026-12-20"],
                              description="Dia da saída; com ele, o horário de funcionamento é o do dia da semana certo")
    veiculo: Literal["carro", "moto", "bicicleta"] | None = Field(
        None, description="Decide as horas ao volante por dia; sem ele, vale o veículo da viagem")


class RoteiroDaViagem(BaseModel):
    usar_ia: bool = False
    contexto: ContextoRoteiro = ContextoRoteiro()


class EdicaoDoRoteiro(BaseModel):
    itens: list[str] = Field(max_length=500, description="Ids dos lugares, na ordem de visita; quem falta sai do roteiro")


class Triagem(BaseModel):
    respostas: list[dict] = []
    pular: bool = False


class AjustePerfil(BaseModel):
    """O que a pessoa muda no perfil; só as chaves enviadas são gravadas."""
    model_config = ConfigDict(extra="forbid")
    # Os padrões não são gravados (exclude_unset); só não aceitam null, que a coluna não guarda
    tema: Literal["claro", "escuro", "sistema"] = "sistema"
    intervalo_km: float = Field(200, ge=10, le=600, description="Distância padrão entre paradas, como na viagem")
    resumo: str = Field("", max_length=preferencias.MAX_TEXTO, description="Resumo da triagem corrigido; vazio apaga")


class Ranquear(BaseModel):
    cards: list[Card]
    resumo: str = ""


@app.post("/viagem", status_code=202)
def viagem(req: Viagem, eu: Usuario = Depends(usuario_atual)):
    entrada = req.model_dump(mode="json")  # a data vira "AAAA-MM-DD", que vai no JSON do job
    with banco.conectar() as con:  # viagem e job na mesma transação: a viagem aparece já "buscando"
        banco.garantir_usuario(eu.id, eu.email, con)
        vid = viagens.criar(con, eu.id, entrada)
        jid = fila.criar("viagem", {**entrada, "usuario": eu.id, "viagem": vid}, usuario=eu.id, con=con)
        viagens.ligar_job(con, vid, jid)
    metricas.registrar(eu.id, "viagem_criada", vid)
    return {"job_id": jid, "viagem_id": vid, "status": "pendente"}


@app.get("/viagens")
def lista_de_viagens(eu: Usuario = Depends(usuario_atual)):
    return {"viagens": viagens.listar(eu.id)}


@app.get("/cidades")
def buscar_cidades(q: str = Query(min_length=cidades.MINIMO_LETRAS, max_length=80, examples=["vitoria da"]),
                   eu: Usuario = Depends(usuario_atual)):
    """Até 8 municípios no formato "Cidade, UF", para os campos de origem e destino."""
    return cidades.buscar(q)


@app.get("/viagens/{viagem_id}")
def uma_viagem(viagem_id: str, eu: Usuario = Depends(usuario_atual)):
    v = viagens.obter(eu.id, viagem_id)  # viagem de outra pessoa: 404, como se não existisse
    if not v:
        raise HTTPException(404, "Viagem não encontrada")
    return v


@app.get("/jobs/{job_id}")
def job(job_id: str, eu: Usuario = Depends(usuario_atual)):
    j = fila.obter(job_id, usuario=eu.id)  # job de outra pessoa: 404, como se não existisse
    if not j:
        raise HTTPException(404, "Viagem não encontrada")
    return j


class ApagarConta(BaseModel):
    confirmar: str = Field(description='Precisa ser exatamente "APAGAR"', examples=["APAGAR"])


class PushToken(BaseModel):
    """Token do aparelho, ou null para parar de avisar (saída da conta ou aviso desligado)."""
    model_config = ConfigDict(extra="forbid")
    token: str | None


@app.post("/eu/push-token")
def guardar_push_token(req: PushToken, eu: Usuario = Depends(usuario_atual)):
    try:
        push.guardar_token(eu.id, req.token)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return {"ok": True}


@app.get("/eu/exportar")
def exportar_meus_dados(eu: Usuario = Depends(usuario_atual)):
    """LGPD: tudo o que o Desvio guarda da pessoa, em JSON."""
    banco.garantir_usuario(eu.id, eu.email)  # conta apagada ou com exclusão pendente: 401
    return JSONResponse(jsonable_encoder(conta.exportar(eu.id)),
                        headers={"Content-Disposition": 'attachment; filename="desvio-meus-dados.json"'})


LINK_EXPORTAR_MIN = 10


@app.post("/eu/exportar/link")
def link_para_exportar(eu: Usuario = Depends(usuario_atual)):
    """Um link de download dos dados, de uso único e válido por 10 minutos.

    O app abre o link no navegador, que baixa o arquivo: o JSON inteiro passa de 1 MB numa
    viagem longa, e o compartilhar do Android recusa texto desse tamanho. O link não leva o
    token de login, só um código aleatório guardado em `cache`.
    """
    banco.garantir_usuario(eu.id, eu.email)
    codigo = secrets.token_urlsafe(24)
    with banco.conectar() as con:
        con.execute("insert into cache (chave, valor) values (%s, %s)",
                    (f"exportar|{codigo}", Jsonb({"usuario": eu.id})))
    return {"caminho": f"/eu/exportar/arquivo/{codigo}", "valido_min": LINK_EXPORTAR_MIN}


@app.get("/eu/exportar/arquivo/{codigo}")
def baixar_exportacao(codigo: str):
    """Baixa os dados pelo link de `POST /eu/exportar/link`; usado uma vez, o link para de valer."""
    with banco.conectar() as con:
        l = con.execute("delete from cache where chave = %s and guardado_em > now() - make_interval(mins => %s) "
                        "returning valor", (f"exportar|{codigo}", LINK_EXPORTAR_MIN)).fetchone()
    if not l:
        raise HTTPException(404, "Link vencido ou já usado. Peça a exportação de novo no app.")
    return JSONResponse(jsonable_encoder(conta.exportar(l["valor"]["usuario"])),
                        headers={"Content-Disposition": 'attachment; filename="desvio-meus-dados.json"'})


@app.delete("/eu")
def apagar_minha_conta(req: ApagarConta, eu: Usuario = Depends(usuario_atual)):
    """LGPD: apaga os dados na hora e a conta no Supabase Auth (ou em até 15 dias, se ele falhar)."""
    if req.confirmar != conta.CONFIRMACAO:
        raise HTTPException(422, 'Para apagar a conta, confirme com "APAGAR".')
    return conta.apagar(eu.id)


@app.post("/swipe")
def swipe(req: Swipe, eu: Usuario = Depends(usuario_atual)):
    if not preferencias.ID_VALIDO.fullmatch(req.card.id):
        raise HTTPException(422, "Card sem id válido")
    try:
        # uma transação, com garantir_usuario; viagem e parada só se forem desta pessoa
        preferencias.registrar(eu.id, req.card.model_dump(exclude_unset=True), req.tipo, eu.email,
                               viagem=req.viagem, parada=req.parada)
    except preferencias.NaoEncontrado as e:
        raise HTTPException(404, str(e)) from None
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    metricas.registrar(eu.id, "swipe", req.viagem, {"tipo": req.tipo})
    return {"ok": True}


@app.delete("/swipe/{lugar_id:path}")
def desfazer_swipe(lugar_id: str, eu: Usuario = Depends(usuario_atual)):
    """Tira a decisão desta pessoa sobre o lugar. O card volta para a fila da parada."""
    try:
        achou = preferencias.desfazer(eu.id, lugar_id, eu.email)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    if not achou:
        raise HTTPException(404, "Decisão não encontrada")
    return {"ok": True}


@app.get("/perfil")
def perfil(eu: Usuario = Depends(usuario_atual)):
    return preferencias.perfil(eu.id)


@app.patch("/perfil")
def ajustar_perfil(req: AjustePerfil, eu: Usuario = Depends(usuario_atual)):
    """Tema, intervalo padrão entre paradas e resumo da triagem; devolve o perfil inteiro."""
    preferencias.ajustar(eu.id, eu.email, req.model_dump(exclude_unset=True))
    return preferencias.perfil(eu.id)


@app.post("/roteiro")
async def roteiro_da_viagem(req: Roteiro, eu: Usuario = Depends(usuario_atual)):
    if not req.usar_ia:
        return {"itens": roteiro.ordenar_na_rota(_dicts(req.cards)), "explicacoes": {}, "fonte": "geometria"}
    async with httpx.AsyncClient() as client:
        return await ia.ajustar_roteiro(client, _dicts(req.cards), req.contexto)


@app.post("/viagens/{viagem_id}/roteiro")
async def roteiro_guardado(viagem_id: str, req: RoteiroDaViagem | None = None,
                           eu: Usuario = Depends(usuario_atual)):
    """Monta o roteiro com os lugares de Bora ou Favorito da viagem e guarda.

    Pelo km; com `usar_ia`, ajustado pela IA à hora de saída e aos dias do `contexto`,
    com uma explicação por lugar. Se a IA falhar, volta a ordem pelo km (`fonte` "geometria").
    Depois que a pessoa edita (PUT), fica a ordem dela, sem os lugares que ela tirou.

    Sem `saida` ou `data` no contexto, valem as da viagem (Nova viagem). Os dias acabam
    nas estadias que a coleta planejou, e `noites` traz o hotel aceito em cada uma, ou o
    aviso de que falta escolher onde dormir (issue #104).
    """
    req = req or RoteiroDaViagem()
    r = await run_in_threadpool(viagens.lugares_do_roteiro, eu.id, viagem_id)
    if r is None:  # viagem de outra pessoa: 404, como se não existisse
        raise HTTPException(404, "Viagem não encontrada")
    plano = await run_in_threadpool(viagens.planejamento, viagem_id) or {}
    estadias = plano.get("estadias") or []
    if r["fonte"] != "pessoa" and req.usar_ia:
        contexto = req.contexto.model_dump(mode="json", exclude_none=True)
        for chave in ("saida", "data"):
            if chave not in contexto and plano.get(chave):
                contexto[chave] = plano[chave]
        veiculo = contexto.get("veiculo") or plano.get("veiculo")
        async with httpx.AsyncClient() as client:
            r = await ia.ajustar_roteiro(client, r["itens"], contexto, veiculo, estadias)
    if r["fonte"] != "pessoa" and not await run_in_threadpool(viagens.guardar_roteiro, viagem_id, r):
        # a pessoa editou enquanto a IA respondia: vale a ordem dela
        r = await run_in_threadpool(viagens.lugares_do_roteiro, eu.id, viagem_id)
    # a ordem que a pessoa escolheu não volta para a IA, nem é regravada: só o PUT a grava
    # Abrir a aba Roteiro sem nenhum Bora não conta como "chegou ao roteiro".
    if r.get("itens"):
        await run_in_threadpool(metricas.registrar, eu.id, "roteiro_montado", viagem_id)
    return _com_noites(r, estadias)


def _com_noites(r: dict, estadias: list[dict]) -> dict:
    """O roteiro com `noites`: uma por estadia, com o hotel aceito ou o aviso do que falta."""
    return {**r, "noites": roteiro.noites(r["itens"], estadias)}


@app.put("/viagens/{viagem_id}/roteiro")
def roteiro_editado(viagem_id: str, req: EdicaoDoRoteiro, eu: Usuario = Depends(usuario_atual)):
    """Guarda o roteiro na ordem da pessoa: reordenar e remover, sem apagar a decisão Bora."""
    try:
        r = viagens.editar_roteiro(eu.id, viagem_id, req.itens)
    except ValueError:
        raise HTTPException(422, "Esse lugar não está no roteiro desta viagem.")
    if r is None:  # viagem de outra pessoa: 404, como se não existisse
        raise HTTPException(404, "Viagem não encontrada")
    return _com_noites(r, (viagens.planejamento(viagem_id) or {}).get("estadias") or [])


@app.post("/triagem")
async def triagem(req: Triagem, eu: Usuario = Depends(usuario_atual)):
    """Pergunta seguinte, ou o fim. Concluir e Pular gravam em `usuario.perfil_gosto`."""
    if req.pular:
        # Pular não chama a IA: guarda as respostas até aqui e segue sem resumo
        preferencias.guardar_triagem(eu.id, eu.email, req.respostas, None, pulou=True)
        metricas.registrar(eu.id, "triagem_pulada")
        return {"pergunta": None, "opcoes": [], "fim": True, "resumo": None, "fonte": "fixa", "pulou": True}
    async with httpx.AsyncClient() as client:
        r = await ia.triagem(client, req.respostas)
    if r.get("fim"):
        preferencias.guardar_triagem(eu.id, eu.email, req.respostas, r.get("resumo"), pulou=False)
        metricas.registrar(eu.id, "triagem_concluida")
    return r


@app.post("/cards/ranquear")
async def ranquear(req: Ranquear, eu: Usuario = Depends(usuario_atual)):
    async with httpx.AsyncClient() as client:
        return await ia.ranquear(client, _dicts(req.cards), req.resumo)


@app.get("/fotos/{nome:path}", include_in_schema=False)
async def foto(nome: str, l: int = Query(gmaps.LARGURA_FOTO, ge=100, le=1600), ass: str = "", exp: int = 0):
    """Foto da Places API sem expor a chave: confere assinatura e validade e redireciona para a imagem no Google."""
    if not gmaps.foto_valida(nome, l, ass, exp):
        raise HTTPException(404, "Foto não encontrada")
    async with httpx.AsyncClient() as client:
        destino = await gmaps.url_da_foto(client, nome, l)
    if not destino:
        raise HTTPException(404, "Foto não encontrada")
    return RedirectResponse(destino, status_code=302, headers={"Cache-Control": "private, max-age=3600"})


class EventoCliente(BaseModel):
    """O que só o app vê: abrir o mapa e o instante em que o primeiro card apareceu."""
    model_config = ConfigDict(extra="forbid")
    evento: Literal["roteiro_aberto_mapa", "primeiro_card"]
    viagem: str
    tempo_ms: int | None = Field(None, ge=0, le=3_600_000)
    app: Literal["google", "waze"] | None = None

    @model_validator(mode="after")
    def confere(self):
        if self.evento == "roteiro_aberto_mapa" and self.app is None:
            raise ValueError("Informe o app de mapas")
        if self.evento == "primeiro_card" and self.tempo_ms is None:
            raise ValueError("Informe o tempo até o primeiro card")
        return self


def _viagem_da_pessoa(usuario: str, viagem: str) -> str:
    try:
        viagem = str(uuid.UUID(viagem))
    except ValueError:
        raise HTTPException(422, "Viagem inválida") from None
    with banco.conectar() as con:
        if not con.execute("select 1 from viagem where id = %s and usuario = %s", (viagem, usuario)).fetchone():
            raise HTTPException(404, "Viagem não encontrada")
    return viagem


@app.post("/eventos")
def eventos(req: EventoCliente, eu: Usuario = Depends(usuario_atual)):
    """Evento que só acontece no celular. O corpo não aceita campo além dos técnicos."""
    viagem = _viagem_da_pessoa(eu.id, req.viagem)
    if req.evento == "roteiro_aberto_mapa":
        metricas.registrar(eu.id, req.evento, viagem, {"app": req.app})
    else:
        metricas.registrar(eu.id, req.evento, viagem, {"origem": "app", "tempo_ms": req.tempo_ms})
    return {"ok": True}


def _painel_admin(x_admin_token: str | None) -> None:
    esperado = os.getenv("PV_ADMIN_TOKEN")
    if not esperado or not x_admin_token or not secrets.compare_digest(x_admin_token, esperado):
        raise HTTPException(404, "Não encontrado")


@app.get("/metricas", include_in_schema=False)
def metricas_do_produto(x_admin_token: str | None = Header(None)):
    """As seis metas do PRD. Só com PV_ADMIN_TOKEN; sem ele, 404, como /uso/ia."""
    _painel_admin(x_admin_token)
    return metricas.painel()


@app.get("/uso/ia", include_in_schema=False)
def uso_da_ia(dias: int = Query(7, ge=1, le=90), x_admin_token: str | None = Header(None)):
    """Uso diário do Groq por modelo (painel da #41). Só com PV_ADMIN_TOKEN; sem ele, 404."""
    _painel_admin(x_admin_token)
    return {"cota_requisicoes_dia": uso_ia.COTA_REQUISICOES_DIA, "cota_tokens_dia": uso_ia.COTA_TOKENS_DIA,
            "dias": uso_ia.resumo(dias)}
