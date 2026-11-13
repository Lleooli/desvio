import { useId, useState, type ReactNode } from "react";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Defs, G, Path, RadialGradient, Rect, Stop } from "react-native-svg";
import { espaco, medida, raio, useCores, type Cor } from "@/tema";

export type VarianteCeu = "faixa" | "placa";

type Brilho = {
  cor: Cor;
  /** Canto do brilho, em fração da largura e da altura. */
  x: 0 | 1;
  y: 0 | 1;
  /** Raios da elipse, em fração da largura e da altura. */
  rx: number;
  ry: number;
  /** Onde o brilho some, em fração do raio. */
  fim: number;
};

// Os mesmos radial-gradient de .dv-ceu e .dv-ceu--placa em docs/design/design-system/components/bundle.css.
const brilhos: Record<VarianteCeu, Brilho[]> = {
  faixa: [
    { cor: "ceu-azul", x: 0, y: 0, rx: 0.64, ry: 0.74, fim: 0.64 },
    { cor: "ceu-claro", x: 1, y: 0, rx: 0.54, ry: 0.64, fim: 0.62 },
    { cor: "ceu-sol", x: 0, y: 1, rx: 0.62, ry: 0.7, fim: 0.66 },
    { cor: "ceu-faixa", x: 1, y: 1, rx: 0.56, ry: 0.66, fim: 0.64 },
  ],
  placa: [
    { cor: "ceu-azul", x: 0, y: 0, rx: 0.64, ry: 0.74, fim: 0.64 },
    { cor: "ceu-placa", x: 1, y: 0, rx: 0.56, ry: 0.66, fim: 0.64 },
    { cor: "ceu-sol", x: 0, y: 1, rx: 0.6, ry: 0.7, fim: 0.66 },
    { cor: "ceu-claro", x: 1, y: 1, rx: 0.52, ry: 0.62, fim: 0.62 },
  ],
};

// Um "dente" do perfil de morros, repetido na largura (máscara de .dv-ceu--serra).
const morro = "M0 28V20C14 20 22 6 38 6s20 12 34 12 18-14 34-14 22 16 36 16c8 0 12-4 18-4v12Z";

/** Só o gradiente do céu, preenchendo o pai. Fundo do Ceu e da JanelaCidade sem foto. */
export function FundoCeu({ variante = "faixa" }: { variante?: VarianteCeu }) {
  const { c } = useCores();
  // O useId do React traz caracteres que não valem dentro de url(#…).
  const prefixo = "ceu" + useId().replace(/[^a-zA-Z0-9]/g, "");
  const lista = brilhos[variante];
  return (
    <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" aria-hidden>
      <Defs>
        {lista.map((b, i) => (
          // Elipse no canto: o raio 1 da caixa vira rx × ry pela transformação.
          <RadialGradient
            key={b.cor}
            id={`${prefixo}${i}`}
            gradientUnits="objectBoundingBox"
            cx={0}
            cy={0}
            fx={0}
            fy={0}
            r={1}
            gradientTransform={`translate(${b.x} ${b.y}) scale(${b.rx} ${b.ry})`}
          >
            <Stop offset={0} stopColor={c[b.cor]} stopOpacity={1} />
            <Stop offset={b.fim} stopColor={c[b.cor]} stopOpacity={0} />
          </RadialGradient>
        ))}
      </Defs>
      <Rect width="100%" height="100%" fill={c["ceu-base"]} />
      {lista.map((b, i) => (
        <Rect key={b.cor} width="100%" height="100%" fill={`url(#${prefixo}${i})`} />
      ))}
    </Svg>
  );
}

type Props = {
  children?: ReactNode;
  /** "faixa" (padrão) ou "placa", que troca o brilho do alto à direita pelo verde. */
  variante?: VarianteCeu;
  /** Recorta a base com o perfil de serra, na cor de `fundoSerra`. */
  serra?: boolean;
  /** Superfície que vem logo abaixo do céu; padrão surface-100. */
  fundoSerra?: Cor;
  /** Cantos radius-lg, para usar como bloco dentro da tela. */
  arredondado?: boolean;
  style?: StyleProp<ViewStyle>;
};

/** Céu de fim de tarde para o topo das telas de entrada. Uma vez por tela; texto em ink e ink-muted. */
export function Ceu({ children, variante = "faixa", serra = false, fundoSerra = "surface-100", arredondado = false, style }: Props) {
  const { c } = useCores();
  const [largura, setLargura] = useState(0);
  const morros = Math.ceil(largura / medida.serraPadrao);

  return (
    <View
      onLayout={serra ? (e) => setLargura(e.nativeEvent.layout.width) : undefined}
      style={[s.ceu, arredondado && s.arredondado, style]}
    >
      <FundoCeu variante={variante} />
      <View style={[s.conteudo, serra && s.conteudoSerra]}>{children}</View>
      {serra && morros > 0 ? (
        <Svg style={s.serra} width={largura} height={medida.serraAltura} aria-hidden>
          {Array.from({ length: morros }, (_, i) => (
            <G key={i} transform={`translate(${i * medida.serraPadrao} 0)`}>
              <Path d={morro} fill={c[fundoSerra]} />
            </G>
          ))}
        </Svg>
      ) : null}
    </View>
  );
}

const s = StyleSheet.create({
  ceu: { position: "relative" },
  arredondado: { borderRadius: raio["radius-lg"], overflow: "hidden" },
  conteudo: {
    paddingTop: espaco["space-8"],
    paddingHorizontal: espaco["space-4"],
    paddingBottom: espaco["space-6"],
  },
  conteudoSerra: { paddingBottom: espaco["space-6"] + medida.serraAltura },
  // -1 cobre a costura de meio pixel entre a serra e a superfície de baixo.
  serra: { position: "absolute", left: 0, bottom: -1 },
});
