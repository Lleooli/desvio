// Testes de src/mapas.ts com o test runner do Node, sem dependência nova:
// npm test (o Node lê o .ts tirando os tipos).
import assert from "node:assert/strict";
import { test } from "node:test";
import { trechosGoogleMaps } from "./mapas.ts";

/** Lugares com coordenadas; o de índice `semCidade` vem sem o campo `cidade`. */
function lugares(quantos, semCidade = -1) {
  return Array.from({ length: quantos }, (_, i) => ({
    id: String(i),
    nome: `Bem Vindo a Lugar ${i}`,
    ...(i === semCidade ? {} : { cidade: `Cidade ${i}` }),
    lat: -10 - i,
    lon: -50 - i,
  }));
}

test("as pontas dos trechos mostram a cidade do lugar, e a origem e o destino da viagem", () => {
  // 25 lugares: 3 trechos (o Google aceita 9 paradas por rota).
  const trechos = trechosGoogleMaps("Alegrete, RS", "Vitória da Conquista, BA", lugares(25), "carro");
  assert.deepEqual(
    trechos.map((t) => [t.de, t.ate]),
    [
      ["Alegrete, RS", "Cidade 9"],
      ["Cidade 9", "Cidade 19"],
      ["Cidade 19", "Vitória da Conquista, BA"],
    ],
  );
});

test("sem cidade no card, a ponta do trecho usa o nome do lugar", () => {
  const trechos = trechosGoogleMaps("Alegrete, RS", "Vitória da Conquista, BA", lugares(25, 9), "carro");
  assert.equal(trechos[0].ate, "Bem Vindo a Lugar 9");
  assert.equal(trechos[1].de, "Bem Vindo a Lugar 9");
});

test("a URL dos trechos continua com as coordenadas dos lugares", () => {
  const [primeiro] = trechosGoogleMaps("Alegrete, RS", "Vitória da Conquista, BA", lugares(25), "bicicleta");
  const url = new URL(primeiro.url);
  assert.equal(url.searchParams.get("origin"), "Alegrete, RS");
  assert.equal(url.searchParams.get("destination"), "-19,-59");
  assert.equal(url.searchParams.get("waypoints").split("|").length, 9);
  assert.equal(url.searchParams.get("travelmode"), "bicycling");
});
