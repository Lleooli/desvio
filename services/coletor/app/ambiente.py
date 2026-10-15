"""Lê o .env da raiz do repositório em execução local (o docker compose já faz isso sozinho).

Só preenche variáveis que ainda não existem no ambiente, e roda antes dos outros
módulos do app, que leem as variáveis ao serem importados.
"""
from __future__ import annotations

import os
from pathlib import Path


def carregar(caminho: Path) -> None:
    try:
        linhas = Path(caminho).read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave, valor = chave.strip(), valor.strip().strip('"').strip("'")
        if chave and valor:
            os.environ.setdefault(chave, valor)


def procurar(inicio: Path, niveis: int = 4) -> Path | None:
    """O primeiro .env subindo a partir de `inicio` (services/coletor → raiz do repo)."""
    for pasta in [inicio, *inicio.parents][:niveis + 1]:
        if (pasta / ".env").is_file():
            return pasta / ".env"
    return None
