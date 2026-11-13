import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { Image, StyleSheet, useWindowDimensions, View } from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, {
  Easing,
  Extrapolation,
  interpolate,
  runOnJS,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { espaco } from "@/tema";
import { SwipeActions } from "./SwipeActions";
import { Carimbo, SwipeCard, type CardLugar, type Decisao } from "./SwipeCard";

type Props = {
  /** Os cards ainda sem decisão; o primeiro é o do topo. Quem usa tira o card da lista em `onDecisao`. */
  cards: CardLugar[];
  /** Chamada quando o card termina de sair, pelo gesto ou pelo botão. */
  onDecisao: (card: CardLugar, decisao: Decisao) => void;
};

// Movimento do swipe em docs/design/DESIGN-SYSTEM.md (Movimento) e bundle.css (--t-folha, --ease-folha).
const LIMIAR = 0.3;
const GIRO_MAXIMO = 12;
const DURACAO_SAIDA = 420;
const EASE_FOLHA = Easing.bezier(0.32, 0.72, 0, 1);
const LARGURA_MAXIMA = 380;
const PROPORCAO = 3 / 4.3;

/**
 * Decide o que um arrasto significa: direita Bora, esquerda Passo, cima Favorito.
 * Abaixo de ~30% da largura não decide nada e o card volta ao centro.
 *
 * @param x - Deslocamento horizontal do dedo, em px.
 * @param y - Deslocamento vertical do dedo, em px (negativo é para cima).
 * @param largura - Largura do card, em px.
 * @returns A decisão, ou null quando o card deve voltar.
 */
export function decisaoDoArrasto(x: number, y: number, largura: number): Decisao | null {
  "worklet";
  const limiar = largura * LIMIAR;
  if (-y > limiar && -y > Math.abs(x)) return "favorito";
  if (x > limiar) return "bora";
  if (x < -limiar) return "passo";
  return null;
}

/** A pilha do swipe: card do topo com gesto, o próximo já carregado atrás e os botões embaixo. */
export function PilhaSwipe({ cards, onDecisao }: Props) {
  const { width } = useWindowDimensions();
  const largura = Math.min(width - 2 * espaco["space-4"], LARGURA_MAXIMA);
  const topo = useRef<{ decidir: (decisao: Decisao) => void }>(null);
  const [saindo, setSaindo] = useState(false);
  const [atual, proximo] = cards;

  // O próximo card está montado atrás do topo, então a foto dele já baixou; o seguinte vai no cache.
  useEffect(() => {
    const foto = cards[2]?.foto;
    if (foto) Image.prefetch(foto).catch(() => {});
  }, [cards]);

  useEffect(() => setSaindo(false), [atual?.id]);

  if (!atual) return null;

  const decidir = (card: CardLugar, decisao: Decisao) => onDecisao(card, decisao);
  const porBotao = (decisao: Decisao) => {
    if (saindo) return;
    setSaindo(true);
    topo.current?.decidir(decisao);
  };

  return (
    <View style={s.pilha}>
      <View style={{ width: largura, aspectRatio: PROPORCAO }}>
        {proximo ? (
          <View style={StyleSheet.absoluteFill} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
            <SwipeCard card={proximo} atras />
          </View>
        ) : null}
        <CardDoTopo
          key={atual.id}
          ref={topo}
          card={atual}
          largura={largura}
          onSaida={() => setSaindo(true)}
          onDecisao={decidir}
        />
      </View>
      <SwipeActions
        disabled={saindo}
        onPasso={() => porBotao("passo")}
        onFavorito={() => porBotao("favorito")}
        onBora={() => porBotao("bora")}
      />
    </View>
  );
}

type CardDoTopoProps = {
  card: CardLugar;
  largura: number;
  onSaida: () => void;
  onDecisao: (card: CardLugar, decisao: Decisao) => void;
  ref: Ref<{ decidir: (decisao: Decisao) => void }>;
};

/** Montado de novo a cada card (key = id), então o deslocamento sempre começa em zero. */
function CardDoTopo({ card, largura, onSaida, onDecisao, ref }: CardDoTopoProps) {
  const menosMovimento = useReducedMotion();
  const x = useSharedValue(0);
  const y = useSharedValue(0);
  const limiar = largura * LIMIAR;

  const concluir = (decisao: Decisao) => onDecisao(card, decisao);

  /** Leva o card para fora da tela e registra a decisão; com menos movimento, troca na hora. */
  const sair = (decisao: Decisao) => {
    "worklet";
    if (menosMovimento) {
      runOnJS(concluir)(decisao);
      return;
    }
    const destinoX = decisao === "bora" ? largura * 1.5 : decisao === "passo" ? -largura * 1.5 : x.value;
    const destinoY = decisao === "favorito" ? -largura * 2 : y.value;
    const config = { duration: DURACAO_SAIDA, easing: EASE_FOLHA };
    y.value = withTiming(destinoY, config);
    x.value = withTiming(destinoX, config, (terminou) => {
      if (terminou) runOnJS(concluir)(decisao);
    });
  };

  useImperativeHandle(ref, () => ({ decidir: (decisao: Decisao) => sair(decisao) }));

  const gesto = Gesture.Pan()
    .onUpdate((e) => {
      x.value = e.translationX;
      y.value = e.translationY;
    })
    .onEnd((e) => {
      const decisao = decisaoDoArrasto(e.translationX, e.translationY, largura);
      if (decisao) {
        runOnJS(onSaida)();
        sair(decisao);
      } else if (menosMovimento) {
        x.value = 0;
        y.value = 0;
      } else {
        x.value = withSpring(0);
        y.value = withSpring(0);
      }
    });

  const movimento = useAnimatedStyle(() => ({
    transform: [
      { translateX: x.value },
      { translateY: y.value },
      { rotate: `${interpolate(x.value, [-largura, 0, largura], [-GIRO_MAXIMO, 0, GIRO_MAXIMO], Extrapolation.CLAMP)}deg` },
    ],
  }));
  // O carimbo aparece com opacidade proporcional ao arrasto.
  const bora = useAnimatedStyle(() => ({ opacity: interpolate(x.value, [0, limiar], [0, 1], Extrapolation.CLAMP) }));
  const passo = useAnimatedStyle(() => ({ opacity: interpolate(-x.value, [0, limiar], [0, 1], Extrapolation.CLAMP) }));
  const favorito = useAnimatedStyle(() => ({
    opacity: -y.value > Math.abs(x.value) ? interpolate(-y.value, [0, limiar], [0, 1], Extrapolation.CLAMP) : 0,
  }));

  return (
    <GestureDetector gesture={gesto}>
      <Animated.View style={[StyleSheet.absoluteFill, movimento]}>
        <SwipeCard card={card} />
        {(
          [
            ["bora", bora],
            ["passo", passo],
            ["favorito", favorito],
          ] as const
        ).map(([decisao, estilo]) => (
          <Animated.View key={decisao} pointerEvents="none" aria-hidden style={[StyleSheet.absoluteFill, estilo]}>
            <Carimbo decisao={decisao} />
          </Animated.View>
        ))}
      </Animated.View>
    </GestureDetector>
  );
}

const s = StyleSheet.create({
  // SwipeActions já tem space-4 de respiro; somado, dá o space-8 acima dos botões.
  pilha: { alignItems: "center", gap: espaco["space-4"] },
});
