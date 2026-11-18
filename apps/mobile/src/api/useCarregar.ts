/**
 * Carrega um dado da API para uma tela, com o erro já em texto para a pessoa e um jeito
 * de tentar de novo.
 */
import { useCallback, useEffect, useState } from "react";
import { mensagemDeErro } from "./cliente";

export type Carregamento<T> = {
  dados: T | null;
  /** Mensagem curta que diz o que fazer; null sem erro. */
  erro: string | null;
  carregando: boolean;
  tentarDeNovo: () => void;
};

/**
 * Chama `carregar` ao montar e sempre que `chave` muda; com `chave` null, não chama.
 *
 * @param chave - O que identifica o dado (o id da viagem, por exemplo).
 * @param carregar - A chamada à API para essa chave.
 * @returns O dado, o erro, se está carregando e a ação de tentar de novo.
 */
export function useCarregar<T>(chave: string | null, carregar: (chave: string) => Promise<T>): Carregamento<T> {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(chave !== null);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    if (chave === null) return;
    let valendo = true; // resposta de uma chave antiga não sobrescreve a atual
    setCarregando(true);
    setErro(null);
    carregar(chave).then(
      (novo) => valendo && (setDados(novo), setCarregando(false)),
      (e: unknown) => valendo && (setErro(mensagemDeErro(e)), setCarregando(false)),
    );
    return () => {
      valendo = false;
    };
    // `carregar` costuma ser uma função nova a cada render; quem dispara é a chave ou a tentativa.
  }, [chave, tentativa]);

  const tentarDeNovo = useCallback(() => setTentativa((t) => t + 1), []);
  return { dados, erro, carregando, tentarDeNovo };
}
