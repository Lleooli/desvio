"""API do planejador. Rode com:  uvicorn app.main:app --reload

Fluxo pensado para o front (estilo Tinder):
1. POST /viagem (carro, moto ou bicicleta)  → job_id (202); a coleta roda no worker
   GET  /jobs/{id}                          → status; quando "pronto", paradas com cards
2. POST /swipe (um por card deslizado)      → guarda a decisão
3. POST /roteiro                            → ordem de visita dos aceitos, pelo km na rota
4. GET  /perfil/{usuario}                   → resumo do gosto, para a IA

IA (Groq, com plano B sem IA): POST /triagem, POST /cards/ranquear e
POST /roteiro com "usar_ia": true.

O Desvio só monta viagens por terra; o modo avião saiu do escopo.
"""
from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal

from pydantic import BaseModel, Field

from . import fila, ia, preferencias, roteiro

app = FastAPI(title="Planejador de Viagem — coleta de lugares")
ORIGENS = [o.strip() for o in os.getenv("PV_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ORIGENS, allow_methods=["*"], allow_headers=["*"])

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
    usuario: str | None = None


class Swipe(BaseModel):
    usuario: str
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
def viagem(req: Viagem):
    return {"job_id": fila.criar("viagem", req.model_dump()), "status": "pendente"}


@app.get("/jobs/{job_id}")
def job(job_id: str):
    j = fila.obter(job_id)
    if not j:
        raise HTTPException(404, "Viagem não encontrada")
    return j


@app.post("/swipe")
def swipe(req: Swipe):
    preferencias.registrar(req.usuario, req.card, req.gostou)
    return {"ok": True}


@app.get("/perfil/{usuario}")
def perfil(usuario: str):
    return preferencias.perfil(usuario)


@app.post("/roteiro")
async def roteiro_da_viagem(req: Roteiro):
    if not req.usar_ia:
        return {"itens": roteiro.ordenar_na_rota(req.cards), "explicacoes": {}, "fonte": "geometria"}
    async with httpx.AsyncClient() as client:
        return await ia.ajustar_roteiro(client, req.cards, req.contexto)


@app.post("/triagem")
async def triagem(req: Triagem):
    async with httpx.AsyncClient() as client:
        return await ia.triagem(client, req.respostas)


@app.post("/cards/ranquear")
async def ranquear(req: Ranquear):
    async with httpx.AsyncClient() as client:
        return await ia.ranquear(client, req.cards, req.resumo)
