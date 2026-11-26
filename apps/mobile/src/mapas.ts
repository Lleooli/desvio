// Links para abrir o roteiro no app de mapas (HU14). O Desvio não navega curva a curva.
// São links https, que abrem o app instalado no Android e no iOS, ou o site se não houver.
import type { Card, Veiculo } from "@/api";

/** Paradas intermediárias que o Google Maps aceita numa rota no celular. */
export const LIMITE_PARADAS_GOOGLE = 9;

export type Trecho = {
  /** 1, 2, 3…: a ordem do trecho na viagem. */
  numero: number;
  /** Onde o trecho começa e termina, para a pessoa reconhecer: a cidade do lugar, ou o nome se não houver. */
  de: string;
  ate: string;
  url: string;
};

type Ponto = { nome: string; endereco: string };

/** Coordenadas quando o lugar tem; senão o nome com a cidade, para o app de mapas buscar. */
function endereco(lugar: Card): string {
  if (lugar.lat != null && lugar.lon != null) return `${lugar.lat},${lugar.lon}`;
  return [lugar.nome, lugar.cidade, lugar.uf].filter(Boolean).join(", ");
}

/**
 * O roteiro como rotas do Google Maps, da origem ao destino passando pelos lugares.
 *
 * Quando os lugares passam do limite de paradas do Google Maps, a viagem vira trechos
 * encadeados: cada trecho termina no lugar onde o próximo começa.
 *
 * @param origem - Cidade de saída da viagem, como a pessoa escreveu.
 * @param destino - Cidade de chegada.
 * @param lugares - Os itens do roteiro, na ordem.
 * @param veiculo - Bicicleta abre a rota de bicicleta; o resto, a de carro.
 */
export function trechosGoogleMaps(origem: string, destino: string, lugares: Card[], veiculo: Veiculo): Trecho[] {
  const pontos: Ponto[] = [
    { nome: origem, endereco: origem },
    // A ponta do trecho mostra a cidade: o nome do lugar pode ser uma placa ("Bem Vindo a…").
    ...lugares.map((lugar) => ({ nome: lugar.cidade || lugar.nome || "Lugar", endereco: endereco(lugar) })),
    { nome: destino, endereco: destino },
  ];
  const modo = veiculo === "bicicleta" ? "bicycling" : "driving";
  const passo = LIMITE_PARADAS_GOOGLE + 1;
  const trechos: Trecho[] = [];
  for (let inicio = 0; inicio < pontos.length - 1; inicio += passo) {
    const fim = Math.min(inicio + passo, pontos.length - 1);
    const parametros = new URLSearchParams({
      api: "1",
      origin: pontos[inicio].endereco,
      destination: pontos[fim].endereco,
      travelmode: modo,
    });
    const meio = pontos.slice(inicio + 1, fim);
    if (meio.length) parametros.set("waypoints", meio.map((p) => p.endereco).join("|"));
    trechos.push({
      numero: trechos.length + 1,
      de: pontos[inicio].nome,
      ate: pontos[fim].nome,
      url: `https://www.google.com/maps/dir/?${parametros}`,
    });
  }
  return trechos;
}

/** Rota até um lugar no Waze, que só aceita um destino por vez. */
export function linkWaze(lugar: Card): string {
  const parametros =
    lugar.lat != null && lugar.lon != null
      ? new URLSearchParams({ ll: `${lugar.lat},${lugar.lon}`, navigate: "yes" })
      : new URLSearchParams({ q: endereco(lugar), navigate: "yes" });
  return `https://waze.com/ul?${parametros}`;
}
