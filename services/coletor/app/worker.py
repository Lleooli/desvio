"""Worker de coleta. Rode com:  python -m app.worker

Pega um job da fila por vez, roda a coleta (minutos, por causa do gosom) e
grava o resultado. Um job que quebra vira "falhou" e o worker segue.
"""
from __future__ import annotations

import asyncio
import logging
import os

from . import coletor, fila, preferencias

log = logging.getLogger("desvio.worker")
INTERVALO_S = float(os.getenv("PV_WORKER_INTERVALO", "2"))


async def processar(job: dict) -> dict:
    e = dict(job["entrada"])
    usuario = e.pop("usuario", None)
    if job["tipo"] == "carro":
        r = await coletor.planejar_carro(**e)
    elif job["tipo"] == "aviao":
        r = await coletor.planejar_cidades(**e)
    else:
        raise ValueError(f"Tipo de job desconhecido: {job['tipo']}")
    return preferencias.personalizar(r, usuario)


async def rodar_uma_vez() -> bool:
    job = fila.pegar_proximo()
    if not job:
        return False
    try:
        fila.concluir(job["id"], await processar(job))
    except Exception as e:  # o worker não pode morrer por causa de um job
        log.exception("job %s falhou", job["id"])
        fila.falhar(job["id"], str(e) or e.__class__.__name__)
    return True


async def _laco() -> None:
    while True:
        if not await rodar_uma_vez():
            await asyncio.sleep(INTERVALO_S)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_laco())


if __name__ == "__main__":
    main()
