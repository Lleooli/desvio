/**
 * O tema que a pessoa escolheu no perfil (HU17), guardado no aparelho para valer desde a
 * abertura do app, antes de qualquer chamada à API. O padrão segue o sistema.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useSyncExternalStore } from "react";
import type { EscolhaTema } from "@/api";

const CHAVE = "desvio:tema";

type Estado = { escolha: EscolhaTema; carregou: boolean };

let estado: Estado = { escolha: "sistema", carregou: false };
const ouvintes = new Set<() => void>();

function mudar(novo: Estado) {
  estado = novo;
  ouvintes.forEach((ouvir) => ouvir());
}

function valida(valor: string | null): EscolhaTema {
  return valor === "claro" || valor === "escuro" ? valor : "sistema";
}

// Lê uma vez ao abrir o app; se o armazenamento falhar, segue o sistema.
AsyncStorage.getItem(CHAVE)
  .catch(() => null)
  .then((valor) => {
    if (!estado.carregou) mudar({ escolha: valida(valor), carregou: true });
  });

/** Troca o tema na hora e guarda no aparelho. */
export function definirTema(escolha: EscolhaTema): void {
  mudar({ escolha, carregou: true });
  AsyncStorage.setItem(CHAVE, escolha).catch(() => {}); // sem gravar, vale até fechar o app
}

/** O tema escolhido; `carregou` é false enquanto o aparelho ainda não respondeu. */
export function useEscolhaTema(): Estado {
  return useSyncExternalStore(
    (ouvir) => {
      ouvintes.add(ouvir);
      return () => ouvintes.delete(ouvir);
    },
    () => estado,
  );
}
