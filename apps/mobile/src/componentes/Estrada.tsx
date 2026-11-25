import { useEffect, useId, useState } from "react";
import { StyleSheet, Text as TextoNativo, View } from "react-native";
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedProps,
  useReducedMotion,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";
import Svg, { Defs, Path, Text, TextPath } from "react-native-svg";
import { estiloTexto, medida, useCores } from "@/tema";

// Os caminhos de Estrada em docs/design/design-system/components/bundle.js, num viewBox 400x200.
const caminhos = {
  curva: "M-30 150 C 60 150 90 58 190 66 S 310 168 430 104",
  subida: "M-30 182 C 90 176 130 120 210 110 S 330 60 430 26",
} as const;

const separador = "   ·   ";
// Repetições do trecho de cidades, para a pista nunca ficar sem texto.
const vezes = 6;

const TextPathAnimado = Animated.createAnimatedComponent(TextPath);

type Props = {
  /** Cidades da rota, na ordem. */
  cidades: string[];
  variante?: keyof typeof caminhos;
  /**
   * Unidades do viewBox 400x200 por segundo, padrão 36. Como o SVG escala com a largura,
   * a velocidade na tela cresce em aparelhos mais largos. 0 ou menos deixa o texto parado.
   */
  velocidade?: number;
  /** Congela o texto; ele também congela sozinho com "reduzir movimento" ligado. */
  parado?: boolean;
  /** Largura da pista em unidades do viewBox 400x200, padrão 46. */
  largura?: number;
  /** Texto para o leitor de tela; padrão "Rota: cidade, cidade…". */
  rotulo?: string;
};

/**
 * Pista curva com o nome das cidades correndo por ela. É ilustração: a lista de
 * paradas está no StopItem. No máximo uma por tela.
 */
export function Estrada({
  cidades,
  variante = "curva",
  velocidade = medida.estradaVelocidade,
  parado = false,
  largura = medida.estradaLargura,
  rotulo,
}: Props) {
  const { c } = useCores();
  const reduzirMovimento = useReducedMotion();
  const id = "estrada" + useId().replace(/[^a-zA-Z0-9]/g, "");
  const trecho = cidades.map((cidade) => cidade.toLocaleUpperCase("pt-BR")).join(separador) + separador;
  // Comprimento de um trecho, medido num <Text> invisível com a mesma fonte. O tamanho
  // da fonte está em unidades do viewBox, então a medida vale em qualquer largura de tela.
  const [ciclo, setCiclo] = useState(0);
  const deslocamento = useSharedValue(0);

  useEffect(() => {
    cancelAnimation(deslocamento);
    deslocamento.value = 0;
    if (parado || reduzirMovimento || ciclo <= 0 || velocidade <= 0) return;
    deslocamento.value = withRepeat(
      withTiming(-ciclo, { duration: (ciclo / velocidade) * 1000, easing: Easing.linear }),
      -1,
    );
    return () => cancelAnimation(deslocamento);
  }, [ciclo, velocidade, parado, reduzirMovimento, deslocamento]);

  const propsAnimadas = useAnimatedProps(() => ({ startOffset: deslocamento.value }));
  const fonte = estiloTexto("estrada");

  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={rotulo ?? `Rota: ${cidades.join(", ")}`}
      style={s.caixa}
    >
      <View style={s.medida} pointerEvents="none" importantForAccessibility="no-hide-descendants" aria-hidden>
        <TextoNativo
          numberOfLines={1}
          onLayout={(e) => setCiclo(e.nativeEvent.layout.width)}
          style={[fonte, s.textoMedido]}
        >
          {trecho}
        </TextoNativo>
      </View>
      <Svg width="100%" height="100%" viewBox="0 0 400 200">
        <Defs>
          <Path id={id} d={caminhos[variante]} />
        </Defs>
        <Path d={caminhos[variante]} fill="none" stroke={c.faixa} strokeWidth={largura + medida.estradaBorda} strokeLinecap="round" />
        <Path d={caminhos[variante]} fill="none" stroke={c.asfalto} strokeWidth={largura} strokeLinecap="round" />
        <Text
          fill={c["on-asfalto"]}
          fontFamily={fonte.fontFamily}
          fontSize={fonte.fontSize}
          letterSpacing={fonte.letterSpacing}
          alignmentBaseline="central"
        >
          <TextPathAnimado href={`#${id}`} animatedProps={propsAnimadas}>
            {trecho.repeat(vezes)}
          </TextPathAnimado>
        </Text>
      </Svg>
    </View>
  );
}

const s = StyleSheet.create({
  caixa: { width: "100%", aspectRatio: 2, overflow: "hidden" },
  // Fora do fluxo e bem larga, para o texto medido não quebrar.
  medida: { position: "absolute", top: 0, left: 0, width: medida.estradaMedicao, opacity: 0 },
  textoMedido: { alignSelf: "flex-start" },
});
