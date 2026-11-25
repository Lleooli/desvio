/**
 * Uma função tipada por rota do coletor (services/coletor/README.md, seção Endpoints).
 * Todas lançam ErroApi, com a mensagem pronta para a tela.
 */
import { chamar, URL_API } from "./cliente";
import type {
  AjustePerfil,
  Card,
  Cidade,
  ContaApagada,
  Job,
  NovaViagem,
  PassoTriagem,
  PedidoRoteiro,
  PedidoRoteiroDaViagem,
  PerfilGosto,
  RespostaTriagem,
  ResumoViagem,
  Roteiro,
  TipoDecisao,
  Viagem,
  ViagemCriada,
} from "./tipos";

export { definirFonteToken, ErroApi, mensagemDeErro, URL_API, type TipoErro } from "./cliente";
export type * from "./tipos";

const id = (valor: string) => encodeURIComponent(valor);

/** Cria a viagem e a busca; a viagem já volta com status `buscando`. */
export const criarViagem = (viagem: NovaViagem) =>
  chamar<ViagemCriada>("/viagem", { metodo: "POST", corpo: viagem });

/** As viagens da pessoa, a mais recente primeiro. */
export const listarViagens = async (): Promise<ResumoViagem[]> =>
  (await chamar<{ viagens: ResumoViagem[] }>("/viagens")).viagens;

/** A viagem com rota e paradas; os cards já avaliados não vêm. */
export const obterViagem = (viagemId: string) => chamar<Viagem>(`/viagens/${id(viagemId)}`);

/** Até 8 municípios no formato "Cidade, UF" para os campos de origem e destino. */
export const buscarCidades = (texto: string) => chamar<Cidade[]>(`/cidades?q=${id(texto)}`);

/** O andamento da busca de uma viagem. */
export const obterJob = (jobId: string) => chamar<Job>(`/jobs/${id(jobId)}`);

/**
 * Grava a decisão sobre um card. Com a viagem e a parada, o card sai da pilha da parada
 * em `GET /viagens/{id}` e conta no progresso dela.
 *
 * @param card - O card como veio da API.
 * @param tipo - Bora, Passo ou Favorito.
 * @param onde - A viagem e a ordem da parada onde a decisão foi tomada.
 */
export const decidir = (card: Card, tipo: TipoDecisao, onde: { viagem?: string; parada?: number } = {}) =>
  chamar<{ ok: true }>("/swipe", { metodo: "POST", corpo: { card, tipo, ...onde } });

/** Desfaz a decisão sobre o lugar; o card volta para a pilha da parada. */
export const desfazerDecisao = (lugarId: string) =>
  chamar<{ ok: true }>(`/swipe/${id(lugarId)}`, { metodo: "DELETE" });

/** Taxas de aceite por categoria, tipo e faixa de preço, resumo da triagem e preferências. */
export const obterPerfilGosto = () => chamar<PerfilGosto>("/perfil");

/** Grava tema, intervalo padrão ou resumo da triagem; devolve o perfil inteiro. */
export const ajustarPerfil = (ajuste: AjustePerfil) =>
  chamar<PerfilGosto>("/perfil", { metodo: "PATCH", corpo: ajuste });

/** Próxima pergunta da triagem, ou `fim` com o resumo do gosto. */
export const responderTriagem = (respostas: RespostaTriagem[]) =>
  chamar<PassoTriagem>("/triagem", { metodo: "POST", corpo: { respostas } });

/** Pular: guarda o que já foi respondido, sem resumo e sem chamar a IA. */
export const pularTriagem = async (respostas: RespostaTriagem[]): Promise<void> => {
  await chamar<unknown>("/triagem", { metodo: "POST", corpo: { respostas, pular: true } });
};

/** Os mesmos cards, os primeiros reordenados pela IA a partir do resumo da triagem. */
export const ranquearCards = (cards: Card[], resumo: string) =>
  chamar<Card[]>("/cards/ranquear", { metodo: "POST", corpo: { cards, resumo } });

/** O roteiro dos cards aceitos, pelo km da estrada ou ajustado pela IA. */
export const montarRoteiro = (pedido: PedidoRoteiro) =>
  chamar<Roteiro>("/roteiro", { metodo: "POST", corpo: pedido });

/**
 * O roteiro da viagem: os lugares com Bora ou Favorito, pelo km da estrada ou, com
 * `usar_ia`, ajustado pela IA à saída e aos dias; o coletor guarda a cada chamada.
 */
export const montarRoteiroDaViagem = (viagemId: string, pedido: PedidoRoteiroDaViagem = {}) =>
  chamar<Roteiro>(`/viagens/${id(viagemId)}/roteiro`, { metodo: "POST", corpo: pedido });

/**
 * Guarda o roteiro na ordem da pessoa; quem fica de fora sai do roteiro, mas o Bora
 * continua. Daí em diante o roteiro volta nessa ordem, sem IA.
 *
 * @param ids - Os ids dos lugares, na ordem de visita.
 */
export const editarRoteiroDaViagem = (viagemId: string, ids: string[]) =>
  chamar<Roteiro>(`/viagens/${id(viagemId)}/roteiro`, { metodo: "PUT", corpo: { itens: ids } });

/** LGPD: tudo o que o Desvio guarda da pessoa. */
export const exportarMeusDados = () => chamar<Record<string, unknown>>("/eu/exportar");

/**
 * LGPD: link de download dos dados, de uso único e válido por 10 minutos. O app abre no
 * navegador, que baixa o arquivo: o JSON passa de 1 MB numa viagem longa, e o compartilhar
 * do Android recusa texto desse tamanho.
 */
export const linkParaExportar = async (): Promise<string> => {
  const { caminho } = await chamar<{ caminho: string; valido_min: number }>("/eu/exportar/link", { metodo: "POST" });
  return URL_API + caminho;
};

/** LGPD: apaga os dados e a conta. */
export const apagarMinhaConta = () =>
  chamar<ContaApagada>("/eu", { metodo: "DELETE", corpo: { confirmar: "APAGAR" } });
