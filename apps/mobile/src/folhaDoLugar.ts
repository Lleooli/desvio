/**
 * A folha do lugar (HU11) abre como modal sobre o swipe. O card e a decisão ficam aqui, na
 * memória: a folha não busca a viagem de novo, e Bora ou Passo nela seguem o mesmo caminho
 * do swipe, na pilha que a abriu.
 */
import { router } from "expo-router";
import type { Card } from "@/api";

export type DecisaoDaFolha = "bora" | "passo";

type FolhaAberta = { card: Card; decidir: (decisao: DecisaoDaFolha) => void };

let aberta: FolhaAberta | null = null;

/**
 * Abre a folha do lugar sobre a tela atual.
 *
 * @param card - O card do topo da pilha.
 * @param decidir - O que a pilha faz com a decisão, igual ao swipe.
 */
export function abrirFolhaDoLugar(card: Card, decidir: (decisao: DecisaoDaFolha) => void): void {
  aberta = { card, decidir };
  router.push({ pathname: "/lugares/[lugarId]", params: { lugarId: card.id } });
}

/** A folha aberta para este lugar; null quando a rota abriu sem a pilha (link direto, app reaberto). */
export function folhaAberta(lugarId: string | undefined): FolhaAberta | null {
  return aberta && aberta.card.id === lugarId ? aberta : null;
}

/** Fecha a folha e, se veio uma decisão, a pilha decide o card como no swipe. */
export function fecharFolhaDoLugar(decisao?: DecisaoDaFolha): void {
  const folha = aberta;
  aberta = null;
  if (router.canGoBack()) router.back();
  else router.replace("/viagens");
  if (folha && decisao) folha.decidir(decisao);
}
