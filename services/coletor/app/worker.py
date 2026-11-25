"""Worker de coleta. Rode com:  python -m app.worker

Pega um job da fila por vez, roda a coleta (minutos, por causa do gosom) e
grava o resultado no job e na viagem (app/viagens.py). Um job que quebra vira "falhou" e o worker segue.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

import httpx

from . import cache, coletor, conta, fila, geo, metricas, preferencias, viagens

log = logging.getLogger("desvio.worker")
INTERVALO_S = float(os.getenv("PV_WORKER_INTERVALO", "2"))
# um job do gosom leva minutos e o worker espera até 30 min por ele sem gravar progresso;
# "rodando" sem mudar por mais que isso (com folga) é worker que morreu
PRESO_MIN = float(os.getenv("PV_JOB_PRESO_MIN", "45"))
# de quanto em quanto tempo o worker tenta de novo as contas que o Supabase Auth não apagou (LGPD)
EXCLUSAO_MIN = float(os.getenv("PV_EXCLUSAO_INTERVALO_MIN", "10"))


async def processar(job: dict) -> dict:
    e = dict(job["entrada"])
    usuario = e.pop("usuario", None)
    viagem = e.pop("viagem", None)  # jobs de antes do #4 não têm viagem
    forcar = e.pop("forcar", False)  # a pessoa pediu lugares novos: recoleta as cidades (#93)
    if job["tipo"] in ("viagem", "carro"):  # "carro": jobs criados antes do veículo existir
        def progresso(etapa: str, titulo: str, detalhe: str, percentual: int) -> None:
            fila.progresso(job["id"], etapa, titulo, detalhe, percentual)

        def parcial(resultado: dict) -> None:
            # Primeiro na viagem (o app abre as paradas e o swipe com ela), depois no job, que
            # avisa a tela Carregando; o personalizar muda `resultado`, então vem por último.
            if viagem:
                try:
                    viagens.gravar_parcial(viagem, resultado)
                except Exception:  # sem o parcial na viagem, a pessoa só espera o final
                    log.warning("não consegui gravar o parcial na viagem %s", viagem, exc_info=True)
            fila.parcial(job["id"], preferencias.personalizar(resultado, usuario))
            metricas.primeiro_card_servidor(usuario, viagem, job["id"], resultado)
        r = await coletor.planejar_viagem(**e, progresso=progresso, parcial=parcial, forcar=forcar)
        metricas.primeiro_card_servidor(usuario, viagem, job["id"], r)
        if viagem:
            viagens.gravar_resultado(viagem, r)  # antes do personalizar, que tira os já avaliados
    else:
        raise ValueError(f"Tipo de job desconhecido: {job['tipo']}")
    # a ordem genérica da IA por cidade já veio da coleta (parada_cidade, #93); o gosto de
    # cada pessoa entra aqui, sem IA: um gosto diferente não gera chamada nova ao Groq
    # (na estadia, personalizar põe os hotéis no topo)
    return preferencias.personalizar(r, usuario)


async def rodar_uma_vez() -> bool:
    job = fila.pegar_proximo()
    if not job:
        return False
    try:
        fila.concluir(job["id"], await processar(job))
    except Exception as e:  # o worker não pode morrer por causa de um job
        log.exception("job %s falhou", job["id"])
        fila.falhar(job["id"], mensagem_amigavel(e))  # o erro completo fica só no log
        if viagem := (job.get("entrada") or {}).get("viagem"):
            try:
                viagens.marcar_falha(viagem)
            except Exception:
                log.exception("não consegui marcar a viagem %s como falhou", viagem)
    return True


ERRO_MAPAS = "Um serviço de mapas não respondeu. Tente de novo em alguns minutos."
ERRO_GENERICO = "Não conseguimos montar a viagem agora. Tente de novo em alguns minutos."


def mensagem_amigavel(e: Exception) -> str:
    """O que /jobs/{id} mostra: nada de URL, host ou traceback."""
    if isinstance(e, geo.ErroConhecido):
        return str(e)
    if isinstance(e, (httpx.HTTPError, TimeoutError)):
        return ERRO_MAPAS
    return ERRO_GENERICO


def completar_exclusoes() -> None:
    """Contas apagadas pelo app que o Supabase Auth ainda não apagou (app/conta.py)."""
    try:
        if feitas := conta.completar_pendentes():
            log.info("%d contas apagadas no Supabase Auth", feitas)
    except Exception:  # tenta de novo na próxima volta
        log.exception("erro ao completar exclusões pendentes")


async def _laco() -> None:
    ultima_exclusao = float("-inf")
    while True:
        if time.monotonic() - ultima_exclusao >= EXCLUSAO_MIN * 60:
            ultima_exclusao = time.monotonic()
            completar_exclusoes()
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
