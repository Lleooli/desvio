/**
 * Viagem ativa: a última viagem aberta, guardada no aparelho. As abas Descobrir e Roteiro
 * mostram essa viagem.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useEffect, useSyncExternalStore } from "react";

const CHAVE = "desvio:viagem-ativa";

type Estado = { id: string | null; carregou: boolean };

let estado: Estado = { id: null, carregou: false };
const ouvintes = new Set<() => void>();

function mudar(novo: Estado) {
  estado = novo;
  ouvintes.forEach((ouvir) => ouvir());
}

// Lê uma vez ao abrir o app; se o armazenamento falhar, fica sem viagem ativa.
AsyncStorage.getItem(CHAVE)
  .catch(() => null)
  .then((id) => {
    if (!estado.carregou) mudar({ id, carregou: true });
  });

/** Marca a viagem como ativa, na memória e no aparelho. */
export function definirViagemAtiva(id: string): void {
  if (estado.carregou && estado.id === id) return;
  mudar({ id, carregou: true });
  AsyncStorage.setItem(CHAVE, id).catch(() => {}); // sem gravar, vale até fechar o app
}

/** A viagem ativa; `carregou` é false enquanto o aparelho ainda não respondeu. */
export function useViagemAtiva(): Estado {
  return useSyncExternalStore(
    (ouvir) => {
      ouvintes.add(ouvir);
      return () => ouvintes.delete(ouvir);
    },
    () => estado,
  );
}

/** Para as telas de /viagens/[id]: abrir a viagem faz dela a ativa. */
export function useMarcarViagemAtiva(id: string | undefined): void {
  useEffect(() => {
    if (id) definirViagemAtiva(id);
  }, [id]);
}
