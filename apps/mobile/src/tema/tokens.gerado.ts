// Gerado por scripts/gerar-tokens.mjs a partir de packages/design-tokens/tokens.json. Não edite à mão.
export const cores = {
  "light": {
    "surface-100": "#F6F2E9",
    "surface-200": "#FFFFFF",
    "surface-300": "#ECE5D6",
    "ink": "#1B1F1D",
    "ink-muted": "#565D59",
    "line": "#D6CDBA",
    "placa": "#0B6B45",
    "on-placa": "#FFFFFF",
    "faixa": "#F2B705",
    "on-faixa": "#1B1F1D",
    "estrela": "#9A6B00",
    "asfalto": "#23292B",
    "on-asfalto": "#F3EFE6",
    "ceu-base": "#FBF1D3",
    "ceu-faixa": "#FFD95C",
    "ceu-placa": "#C2E7D1",
    "ceu-claro": "#FFE89A",
    "ceu-azul": "#C9E4F6",
    "ceu-sol": "#FFCDA8",
    "vidro": "rgba(255, 255, 255, 0.78)",
    "halo-foco": "rgba(242, 183, 5, 0.55)",
    "scrim": "rgba(16, 20, 19, 0.82)",
    "on-scrim": "#FFFFFF",
    "perigo": "#B23A16",
    "foco": "#1B1F1D"
  },
  "dark": {
    "surface-100": "#121614",
    "surface-200": "#1B201E",
    "surface-300": "#272D2A",
    "ink": "#F1EDE4",
    "ink-muted": "#AAB1AC",
    "line": "#3A413D",
    "placa": "#46B985",
    "on-placa": "#0A1F16",
    "faixa": "#F2B705",
    "on-faixa": "#1B1F1D",
    "estrela": "#F2B705",
    "asfalto": "#2C3336",
    "on-asfalto": "#F3EFE6",
    "ceu-base": "#151B18",
    "ceu-faixa": "#3E340E",
    "ceu-placa": "#123F2B",
    "ceu-claro": "#2A2A12",
    "ceu-azul": "#13314A",
    "ceu-sol": "#4A2A14",
    "vidro": "rgba(27, 32, 30, 0.78)",
    "halo-foco": "rgba(242, 183, 5, 0.55)",
    "scrim": "rgba(16, 20, 19, 0.82)",
    "on-scrim": "#FFFFFF",
    "perigo": "#F08A63",
    "foco": "#F2B705"
  }
} as const;
export const sombras = {
  "light": {
    "shadow-1": "0 1px 2px rgba(35, 41, 43, 0.06), 0 4px 12px -4px rgba(35, 41, 43, 0.12)",
    "shadow-2": "0 2px 4px rgba(35, 41, 43, 0.05), 0 22px 44px -18px rgba(35, 41, 43, 0.30)",
    "shadow-card": "0 40px 90px -36px rgba(35, 41, 43, 0.48)",
    "shadow-favorito": "inset 0 1px 0 rgba(255, 255, 255, 0.6), 0 8px 22px -10px rgba(201, 150, 0, 0.7)",
    "shadow-sheet": "0 -4px 16px rgba(35, 41, 43, 0.10)"
  },
  "dark": {
    "shadow-1": "0 1px 2px rgba(0, 0, 0, 0.3), 0 4px 12px -4px rgba(0, 0, 0, 0.5)",
    "shadow-2": "0 2px 4px rgba(0, 0, 0, 0.3), 0 22px 44px -18px rgba(0, 0, 0, 0.7)",
    "shadow-card": "0 40px 90px -36px rgba(0, 0, 0, 0.8)",
    "shadow-favorito": "inset 0 1px 0 rgba(255, 255, 255, 0.6), 0 8px 22px -10px rgba(201, 150, 0, 0.7)",
    "shadow-sheet": "0 -4px 16px rgba(0, 0, 0, 0.45)"
  }
} as const;
export const espaco = {
  "space-1": 4,
  "space-2": 8,
  "space-3": 12,
  "space-4": 16,
  "space-6": 24,
  "space-8": 32,
  "touch": 48,
  "button-h": 52
} as const;
export const raio = {
  "radius-sm": 10,
  "radius-md": 16,
  "radius-lg": 28,
  "radius-arco": 32,
  "radius-pill": 999
} as const;
export const tipografia = {
  "display-xl": {
    "familia": "display",
    "tamanho": 40,
    "altura": 40,
    "peso": 700,
    "espacamento": "-0.035em"
  },
  "display-l": {
    "familia": "display",
    "tamanho": 30,
    "altura": 31,
    "peso": 700,
    "espacamento": "-0.03em"
  },
  "title": {
    "familia": "display",
    "tamanho": 22,
    "altura": 26,
    "peso": 650,
    "espacamento": "-0.02em"
  },
  "km": {
    "familia": "placa",
    "tamanho": 18,
    "altura": 20,
    "peso": 600,
    "espacamento": "0.02em"
  },
  "estrada": {
    "familia": "placa",
    "tamanho": 20,
    "altura": 20,
    "peso": 700,
    "espacamento": "0.14em"
  },
  "body": {
    "familia": "sans",
    "tamanho": 16,
    "altura": 24,
    "peso": 400,
    "espacamento": null
  },
  "body-strong": {
    "familia": "sans",
    "tamanho": 16,
    "altura": 24,
    "peso": 600,
    "espacamento": null
  },
  "body-s": {
    "familia": "sans",
    "tamanho": 14,
    "altura": 20,
    "peso": 400,
    "espacamento": null
  },
  "label": {
    "familia": "sans",
    "tamanho": 13,
    "altura": 16,
    "peso": 600,
    "espacamento": "0.04em"
  },
  "button": {
    "familia": "sans",
    "tamanho": 16,
    "altura": 16,
    "peso": 600,
    "espacamento": null
  }
} as const;
export type Tema = keyof typeof cores;
export type Cor = keyof (typeof cores)["light"];
