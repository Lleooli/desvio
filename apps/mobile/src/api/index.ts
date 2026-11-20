/**
 * Uma função tipada por rota do coletor (services/coletor/README.md, seção Endpoints).
 * Todas lançam ErroApi, com a mensagem pronta para a tela.
 */
import { chamar } from "./cliente";
import type {
  Card,
  Cidade,
  ContaApagada,
  Job,
  NovaViagem,
  PassoTriagem,
  PedidoRoteiro,
  PerfilGosto,
  RespostaTriagem,
  ResumoViagem,
  Roteiro,
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

/** Grava a decisão sobre um card: Bora ou Favorito é `gostou: true`, Passo é `false`. */
export const decidir = (card: Card, gostou: boolean) =>
  chamar<{ ok: true }>("/swipe", { metodo: "POST", corpo: { card, gostou } });

/** Taxas de aceite por categoria, tipo e faixa de preço. */
export const obterPerfilGosto = () => chamar<PerfilGosto>("/perfil");

/** Próxima pergunta da triagem, ou `fim` com o resumo do gosto. */
export const responderTriagem = (respostas: RespostaTriagem[]) =>
  chamar<PassoTriagem>("/triagem", { metodo: "POST", corpo: { respostas } });

/** Os mesmos cards, os primeiros reordenados pela IA a partir do resumo da triagem. */
export const ranquearCards = (cards: Card[], resumo: string) =>
  chamar<Card[]>("/cards/ranquear", { metodo: "POST", corpo: { cards, resumo } });

/** O roteiro dos cards aceitos, pelo km da estrada ou ajustado pela IA. */
export const montarRoteiro = (pedido: PedidoRoteiro) =>
  chamar<Roteiro>("/roteiro", { metodo: "POST", corpo: pedido });

/** O roteiro da viagem: os lugares com Bora ou Favorito, pelo km da estrada; o coletor guarda a cada chamada. */
export const montarRoteiroDaViagem = (viagemId: string) =>
  chamar<Roteiro>(`/viagens/${id(viagemId)}/roteiro`, { metodo: "POST" });

/** LGPD: tudo o que o Desvio guarda da pessoa. */
export const exportarMeusDados = () => chamar<Record<string, unknown>>("/eu/exportar");

/** LGPD: apaga os dados e a conta. */
export const apagarMinhaConta = () =>
  chamar<ContaApagada>("/eu", { metodo: "DELETE", corpo: { confirmar: "APAGAR" } });
