"""Worker de coleta. Rode com:  python -m app.worker

Pega um job da fila por vez, roda a coleta (minutos, por causa do gosom) e
grava o resultado. Um job que quebra vira "falhou" e o worker segue.
"""
from __future__ import annotations

import asyncio
import logging
import os

from . import cache, coletor, fila, preferencias

log = logging.getLogger("desvio.worker")
INTERVALO_S = float(os.getenv("PV_WORKER_INTERVALO", "2"))
# um job do gosom leva minutos; "rodando" sem mudar por mais que isso é worker que morreu
PRESO_MIN = float(os.getenv("PV_JOB_PRESO_MIN", "30"))


async def processar(job: dict) -> dict:
    e = dict(job["entrada"])
    usuario = e.pop("usuario", None)
    if job["tipo"] in ("viagem", "carro"):  # "carro": jobs criados antes do veículo existir
        def progresso(etapa: str, titulo: str, detalhe: str, percentual: int) -> None:
            fila.progresso(job["id"], etapa, titulo, detalhe, percentual)

        def parcial(resultado: dict) -> None:
            fila.parcial(job["id"], preferencias.personalizar(resultado, usuario))
        r = await coletor.planejar_viagem(**e, progresso=progresso, parcial=parcial)
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
        try:
            if fila.recuperar_presos(PRESO_MIN):
                log.warning("jobs presos em 'rodando' voltaram para a fila")
            if await rodar_uma_vez():
                continue
        except Exception:  # banco travado etc.: espera e tenta de novo
            log.exception("erro no laço do worker")
        await asyncio.sleep(INTERVALO_S)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        log.info("cache: %d itens vencidos apagados", cache.apagar_vencidos())
    except Exception:  # limpeza é opcional; o worker sobe mesmo assim
        log.warning("não consegui limpar o cache vencido", exc_info=True)
    asyncio.run(_laco())


if __name__ == "__main__":
    main()
