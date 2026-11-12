// Gera src/tema/tokens.gerado.ts a partir de packages/design-tokens/tokens.json.
// Rode depois de mudar o design system: npm run tokens
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const aqui = dirname(fileURLToPath(import.meta.url));
const origem = resolve(aqui, "../../../packages/design-tokens/tokens.json");
const destino = resolve(aqui, "../src/tema/tokens.gerado.ts");
const t = JSON.parse(readFileSync(origem, "utf8"));

const temas = t.color.themes.map((x) => x.id);
const cores = Object.fromEntries(temas.map((tema) => [tema, {}]));
for (const c of t.color.tokens) {
  for (const tema of temas) {
    const v = typeof c.value === "string" ? c.value : c.value[tema] ?? c.value[temas[0]];
    cores[tema][c.name] = v;
  }
}
const sombras = Object.fromEntries(temas.map((tema) => [tema, {}]));
for (const s of t.shadow.tokens) {
  for (const tema of temas) {
    sombras[tema][s.name] = typeof s.value === "string" ? s.value : s.value[tema] ?? s.value[temas[0]];
  }
}
const px = (v) => Number(String(v).replace("px", ""));
const lista = (fam) => Object.fromEntries((t[fam]?.tokens ?? []).map((x) => [x.name, px(x.value)]));
const estilos = {};
for (const g of t.type.groups) {
  for (const s of g.styles) {
    estilos[s.name] = {
      familia: s.family ?? g.family,
      tamanho: px(s.fontSize),
      altura: px(s.lineHeight),
      peso: s.fontWeight,
      espacamento: s.letterSpacing ?? null,
    };
  }
}

const saida = `// Gerado por scripts/gerar-tokens.mjs a partir de packages/design-tokens/tokens.json. Não edite à mão.
export const cores = ${JSON.stringify(cores, null, 2)} as const;
export const sombras = ${JSON.stringify(sombras, null, 2)} as const;
export const espaco = ${JSON.stringify(lista("spacing"), null, 2)} as const;
export const raio = ${JSON.stringify(lista("radius"), null, 2)} as const;
export const tipografia = ${JSON.stringify(estilos, null, 2)} as const;
export type Tema = keyof typeof cores;
export type Cor = keyof (typeof cores)["light"];
`;
writeFileSync(destino, saida);
console.log("tokens gerados em", destino);
