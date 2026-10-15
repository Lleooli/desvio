"""Coletor do Desvio: coleta de lugares (OSM + Google Maps via gosom), fila de jobs e IA (Groq)."""
import os
from pathlib import Path

from . import ambiente

# PV_ENV_FILE aponta um .env; vazio desliga (os testes fazem isso). Sem ela, procura a partir da pasta atual.
_arquivo = os.getenv("PV_ENV_FILE")
if _arquivo is None:
    _achado = ambiente.procurar(Path.cwd())
    if _achado:
        ambiente.carregar(_achado)
elif _arquivo:
    ambiente.carregar(Path(_arquivo))
