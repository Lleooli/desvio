import { createContext, createElement, useContext, type ReactNode } from "react";
import { useColorScheme, type TextStyle } from "react-native";
import { cores, espaco, raio, sombras, tipografia, type Cor, type Tema } from "./tokens.gerado";

export { espaco, raio, tipografia };
export type { Cor, Tema };

/** Fontes carregadas em app/_layout.tsx (pacotes @expo-google-fonts). */
export const fontes = {
  display: "BricolageGrotesque_700Bold",
  placa: "BarlowCondensed_600SemiBold",
  placaForte: "BarlowCondensed_700Bold",
  sans: "Barlow_400Regular",
  sansForte: "Barlow_600SemiBold",
} as const;

/** Tamanhos de ícone do design system (Iconografia, em DESIGN-SYSTEM.md). */
export const tamanhoIcone = {
  chip: 16,
  botaoSm: 18,
  padrao: 20,
  nav: 22,
  swipe: 28,
} as const;

/**
 * Medidas fixas do design system que não são tokens em tokens.json
 * (valores de docs/design/design-system/components/bundle.css e de DESIGN-SYSTEM.md).
 */
export const medida = {
  botaoSm: 40,
  chip: 32,
  chipFiltro: 42,
  opcaoSegmented: 44,
  acaoToast: 36,
  itemNav: 56,
  pilulaNavLargura: 56,
  pilulaNavAltura: 28,
  borda: 1.5,
  foco: 2,
  haloCampo: 4,
  entradaToast: 380,
  pressionado: 0.97,
  pressionadoRedondo: 0.92,
  botaoSwipe: 64,
  botaoFavorito: 52,
  bordaSwipe: 2,
  desabilitado: 0.45,
  serraAltura: 28,
  serraPadrao: 160,
  estradaVelocidade: 36,
  estradaLargura: 46,
  estradaBorda: 6,
  paradaKm: 76,
  paradaTrilho: 20,
  paradaTrilhoLinha: 4,
  paradaPonto: 16,
  paradaPontoBorda: 3,
  paradaAltura: 72,
  paradaAjusteTopo: 2,
  /** Largura da caixa invisível onde a Estrada mede o texto (bem larga, para não quebrar). */
  estradaMedicao: 10000,
  // Card do swipe: .dv-card e .dv-stamp em docs/design/design-system/components/bundle.css
  cardLarguraMaxima: 380,
  cardProporcao: 3 / 4.3,
  cardIconeSemFoto: 72,
  cardCarimboTopo: 96,
  cardCarimboBorda: 3,
  cardCarimboTexto: 34,
  cardCarimboLinha: 38,
  cardHorasTexto: 13,
  cardHorasLinha: 16,
  // Tela Carregando: docs/design/telas/Carregando.dc.html
  barraBusca: 10,
  marcaEtapa: 28,
  // Roteiro: a faixa da Estrada no cabeçalho e o número de cada item (canvas Roteiro)
  roteiroEstradaAltura: 104,
  roteiroEstradaRecorte: 40,
  roteiroEstradaLargura: 40,
  roteiroNumero: 32,
} as const;

/** Converte um estilo de tipografia do DS no estilo de texto do React Native. */
export function estiloTexto(nome: keyof typeof tipografia): TextStyle {
  const t = tipografia[nome];
  const forte = t.peso >= 600;
  const fontFamily =
    t.familia === "display"
      ? fontes.display
      : t.familia === "placa"
        ? t.peso >= 700
          ? fontes.placaForte
          : fontes.placa
        : forte
          ? fontes.sansForte
          : fontes.sans;
  // O DS usa "em"; o React Native quer px.
  const letterSpacing = t.espacamento ? parseFloat(t.espacamento) * t.tamanho : 0;
  return { fontFamily, fontSize: t.tamanho, lineHeight: t.altura, letterSpacing };
}

const TemaForcado = createContext<Tema | null>(null);

/** Força um tema para tudo dentro dele (catálogo de componentes; depois, a escolha do perfil). */
export function TemaProvider({ tema, children }: { tema: Tema; children: ReactNode }) {
  return createElement(TemaForcado.Provider, { value: tema }, children);
}

/** Cores e sombras do tema atual: o do TemaProvider mais próximo ou, sem ele, o do sistema. */
export function useCores() {
  const forcado = useContext(TemaForcado);
  const esquema = useColorScheme();
  const tema: Tema = forcado ?? (esquema === "dark" ? "dark" : "light");
  return { tema, c: cores[tema], sombra: sombras[tema] };
}
