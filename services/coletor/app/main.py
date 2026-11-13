"""API do planejador. Rode com:  uvicorn app.main:app --reload

Fluxo pensado para o front (estilo Tinder):
1. POST /viagem (carro, moto ou bicicleta)  → job_id e viagem_id (202); a coleta roda no worker
   GET  /jobs/{id}                          → status; quando "pronto", paradas com cards
   GET  /viagens                            → as viagens da pessoa, a mais recente primeiro
   GET  /viagens/{id}                       → paradas e cards ainda não avaliados, pelo gosto
2. POST /swipe (um por card deslizado)      → guarda a decisão
3. POST /roteiro                            → ordem de visita dos aceitos, pelo km na rota
4. GET  /perfil                            → resumo do gosto, para a IA

Toda rota, menos /docs, exige o token do Supabase (Authorization: Bearer);
o usuário sai do token (app/auth.py), nunca do corpo.

IA (Groq, com plano B sem IA): POST /triagem, POST /cards/ranquear e
POST /roteiro com "usar_ia": true.

O Desvio só monta viagens por terra; o modo avião saiu do escopo.
"""
from __future__ import annotations

import os

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Literal

from pydantic import BaseModel, Field

from . import banco, fila, ia, preferencias, roteiro, viagens
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


class Swipe(BaseModel):
    card: dict
    gostou: bool


class Roteiro(BaseModel):
    cards: list[dict]
    usar_ia: bool = False
    contexto: dict = {}


class Triagem(BaseModel):
    respostas: list[dict] = []


class Ranquear(BaseModel):
    cards: list[dict]
    resumo: str = ""


@app.post("/viagem", status_code=202)
def viagem(req: Viagem, eu: Usuario = Depends(usuario_atual)):
    entrada = req.model_dump()
    with banco.conectar() as con:  # viagem e job na mesma transação: a viagem aparece já "buscando"
        banco.garantir_usuario(eu.id, eu.email, con)
        vid = viagens.criar(con, eu.id, entrada)
        jid = fila.criar("viagem", {**entrada, "usuario": eu.id, "viagem": vid}, usuario=eu.id, con=con)
        viagens.ligar_job(con, vid, jid)
    return {"job_id": jid, "viagem_id": vid, "status": "pendente"}


@app.get("/viagens")
def lista_de_viagens(eu: Usuario = Depends(usuario_atual)):
    return {"viagens": viagens.listar(eu.id)}


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


@app.post("/swipe")
def swipe(req: Swipe, eu: Usuario = Depends(usuario_atual)):
    if not isinstance(req.card.get("id"), str) or not preferencias.ID_VALIDO.fullmatch(req.card["id"]):
        raise HTTPException(422, "Card sem id válido")
    preferencias.registrar(eu.id, req.card, req.gostou, eu.email)  # uma transação, com garantir_usuario
    return {"ok": True}


@app.get("/perfil")
def perfil(eu: Usuario = Depends(usuario_atual)):
    return preferencias.perfil(eu.id)


@app.post("/roteiro")
async def roteiro_da_viagem(req: Roteiro, eu: Usuario = Depends(usuario_atual)):
    if not req.usar_ia:
        return {"itens": roteiro.ordenar_na_rota(req.cards), "explicacoes": {}, "fonte": "geometria"}
    async with httpx.AsyncClient() as client:
        return await ia.ajustar_roteiro(client, req.cards, req.contexto)


@app.post("/triagem")
async def triagem(req: Triagem, eu: Usuario = Depends(usuario_atual)):
    async with httpx.AsyncClient() as client:
        return await ia.triagem(client, req.respostas)


@app.post("/cards/ranquear")
async def ranquear(req: Ranquear, eu: Usuario = Depends(usuario_atual)):
    async with httpx.AsyncClient() as client:
        return await ia.ranquear(client, req.cards, req.resumo)
