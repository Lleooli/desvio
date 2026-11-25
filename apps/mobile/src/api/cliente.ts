/**
 * Chamada HTTP ao coletor: URL base, token do Supabase em toda chamada e erro com mensagem
 * curta que diz o que fazer. As telas nunca veem o erro cru.
 */

/** URL do coletor; no .env do app, `EXPO_PUBLIC_API_URL=http://192.168.0.10:8000`. */
export const URL_API = (process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

const LIMITE_MS = 20_000;

type FonteToken = () => Promise<string | null> | string | null;

let fonteToken: FonteToken = () => null;

/** A tela de login (Supabase Auth) diz aqui de onde sai o `access_token` da sessão. */
export function definirFonteToken(fonte: FonteToken): void {
  fonteToken = fonte;
}

export type TipoErro = "sem-rede" | "sessao" | "nao-encontrado" | "pedido" | "servidor";

const MENSAGENS: Record<TipoErro, string> = {
  "sem-rede": "Sem conexão. Confira a internet e tente de novo.",
  sessao: "Sua sessão acabou. Entre de novo.",
  "nao-encontrado": "Não achamos essa viagem. Volte para Minhas viagens.",
  pedido: "Algo no pedido não fechou. Confira os campos e tente de novo.",
  servidor: "O Desvio está com problema agora. Tente de novo em alguns minutos.",
};

/** Erro de uma chamada à API; `message` já é o texto para mostrar à pessoa. */
export class ErroApi extends Error {
  constructor(
    readonly tipo: TipoErro,
    readonly status: number | null = null,
  ) {
    super(MENSAGENS[tipo]);
    this.name = "ErroApi";
  }
}

function tipoDoStatus(status: number): TipoErro {
  if (status === 401 || status === 403) return "sessao";
  if (status === 404) return "nao-encontrado";
  if (status >= 400 && status < 500) return "pedido";
  return "servidor";
}

/** O texto para a pessoa a partir de qualquer erro: o de um ErroApi, ou o de servidor. */
export function mensagemDeErro(erro: unknown): string {
  return erro instanceof ErroApi ? erro.message : MENSAGENS.servidor;
}

/**
 * Chama uma rota do coletor e devolve o JSON da resposta.
 *
 * @param caminho - Rota a partir da raiz, como `/viagens`.
 * @param opcoes - Método e corpo (vira JSON).
 * @returns O corpo da resposta, no tipo que a rota devolve.
 * @throws {@link ErroApi} Sem rede, fora do tempo ou com status de erro.
 */
export async function chamar<T>(
  caminho: string,
  opcoes: { metodo?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"; corpo?: unknown } = {},
): Promise<T> {
  const token = await fonteToken();
  const cabecalhos: Record<string, string> = { Accept: "application/json" };
  if (token) cabecalhos.Authorization = `Bearer ${token}`;
  if (opcoes.corpo !== undefined) cabecalhos["Content-Type"] = "application/json";

  const controle = new AbortController();
  const relogio = setTimeout(() => controle.abort(), LIMITE_MS);
  let resposta: Response;
  try {
    resposta = await fetch(URL_API + caminho, {
      method: opcoes.metodo ?? "GET",
      headers: cabecalhos,
      body: opcoes.corpo === undefined ? undefined : JSON.stringify(opcoes.corpo),
      signal: controle.signal,
    });
  } catch {
    clearTimeout(relogio);
    throw new ErroApi("sem-rede"); // fetch só rejeita sem rede ou no abort do tempo-limite
  }
  if (!resposta.ok) {
    clearTimeout(relogio);
    throw new ErroApi(tipoDoStatus(resposta.status), resposta.status);
  }
  // O tempo-limite vale até o corpo chegar inteiro: um corpo que trava também é abortado.
  try {
    return (await resposta.json()) as T; // o formato é o contrato da rota (tipos.ts)
  } catch {
    throw new ErroApi(controle.signal.aborted ? "sem-rede" : "servidor", resposta.status);
  } finally {
    clearTimeout(relogio);
  }
}
