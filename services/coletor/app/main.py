"""API do planejador. Rode com:  uvicorn app.main:app --reload

Fluxo pensado para o front (estilo Tinder):
1. POST /viagem/carro ou /viagem/aviao      → paradas com cards
2. POST /swipe (um por card deslizado)      → guarda a decisão
3. POST /roteiro/carro ou /roteiro/cidade   → ordem de visita dos aceitos
4. GET  /perfil/{usuario}                   → resumo do gosto, para a IA
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import coletor, preferencias, roteiro

app = FastAPI(title="Planejador de Viagem — coleta de lugares")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

Categoria = str  # turismo | restaurante | posto | natureza | hospedagem


class ViagemCarro(BaseModel):
    origem: str = Field(examples=["Alegrete, RS"])
    destino: str = Field(examples=["Vitória da Conquista, BA"])
    intervalo_km: float = Field(200, ge=50, le=600, description="Distância entre paradas sugeridas")
    categorias: list[Categoria] = ["turismo", "restaurante", "posto"]
    por_categoria: int = Field(5, ge=1, le=20)
    usar_google_maps: bool = False
    buscar_instagram: bool = True
    usuario: str | None = None


class Cidade(BaseModel):
    cidade: str = Field(examples=["Salvador, BA"])
    dias: int = Field(1, ge=1, le=30)


class ViagemAviao(BaseModel):
    cidades: list[Cidade]
    categorias: list[Categoria] = ["turismo", "natureza", "restaurante"]
    por_categoria: int = Field(8, ge=1, le=30)
    usar_google_maps: bool = False
    buscar_instagram: bool = True
    usuario: str | None = None


class Swipe(BaseModel):
    usuario: str
    card: dict
    gostou: bool


class RoteiroCarro(BaseModel):
    cards: list[dict]


class RoteiroCidade(BaseModel):
    cards: list[dict]
    dias: int = 1
    inicio_lat: float | None = None
    inicio_lon: float | None = None


def _personalizar(resultado: dict, usuario: str | None) -> dict:
    """Tira cards já avaliados e ordena os novos pelo gosto do usuário."""
    if not usuario:
        return resultado
    vistos, p = preferencias.ja_vistos(usuario), preferencias.perfil(usuario)
    for parada in resultado["paradas"]:
        parada["cards"] = preferencias.pontuar([c for c in parada["cards"] if c["id"] not in vistos], p)
    return resultado


@app.post("/viagem/carro")
async def viagem_carro(req: ViagemCarro):
    dados = req.model_dump(exclude={"usuario"})
    return _personalizar(await coletor.planejar_carro(**dados), req.usuario)


@app.post("/viagem/aviao")
async def viagem_aviao(req: ViagemAviao):
    r = await coletor.planejar_cidades([c.model_dump() for c in req.cidades], req.categorias,
                                       req.por_categoria, req.usar_google_maps, req.buscar_instagram)
    return _personalizar(r, req.usuario)


@app.post("/swipe")
def swipe(req: Swipe):
    preferencias.registrar(req.usuario, req.card, req.gostou)
    return {"ok": True}


@app.get("/perfil/{usuario}")
def perfil(usuario: str):
    return preferencias.perfil(usuario)


@app.post("/roteiro/carro")
def roteiro_carro(req: RoteiroCarro):
    return roteiro.ordenar_carro(req.cards)


@app.post("/roteiro/cidade")
def roteiro_cidade(req: RoteiroCidade):
    inicio = (req.inicio_lat, req.inicio_lon) if req.inicio_lat is not None and req.inicio_lon is not None else None
    return roteiro.roteiro_cidade(req.cards, req.dias, inicio)
