import { useEffect } from "react";
import { AccessibilityInfo, Platform, Pressable, StyleSheet, Text } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, useCores } from "@/tema";
import { useFoco } from "./foco";
import { Icon, type IconName } from "./Icon";

type Props = {
  /** Uma frase, sem ponto final, nomeando o lugar: "Churrascaria Gaúcha entrou no roteiro". */
  children: string;
  icon?: IconName;
  /** Rótulo da ação, como "Desfazer". */
  acao?: string;
  onAcao?: () => void;
};

/**
 * Confirmação curta depois de uma ação. Quem usa decide onde fica (acima da BottomNav),
 * quanto tempo dura (4 s com Desfazer) e que só existe um por vez.
 */
export function Toast({ children, icon = "check", acao, onAcao }: Props) {
  const { c, sombra } = useCores();
  const foco = useFoco();

  // O Android lê pela liveRegion; o iOS precisa do anúncio explícito. Anunciar nos dois
  // faria o TalkBack falar a frase duas vezes.
  useEffect(() => {
    if (Platform.OS === "ios") AccessibilityInfo.announceForAccessibility(children);
  }, [children]);

  return (
    <Animated.View
      entering={FadeInDown.duration(medida.entradaToast)}
      accessibilityLiveRegion="polite"
      style={[s.toast, { backgroundColor: c.asfalto, boxShadow: sombra["shadow-2"] }]}
    >
      <Icon name={icon} size={tamanhoIcone.padrao} color={c.faixa} />
      <Text style={[estiloTexto("body"), s.texto, { color: c["on-asfalto"] }]}>{children}</Text>
      {acao && onAcao ? (
        <Pressable
          onPress={onAcao}
          {...foco.eventos}
          // A ação tem 36px; o hitSlop completa os 48px de alvo de toque.
          hitSlop={(espaco.touch - medida.acaoToast) / 2}
          accessibilityRole="button"
          accessibilityLabel={acao}
          style={[s.acao, foco.estilo]}
        >
          <Text style={[estiloTexto("button"), { color: c.faixa }]}>{acao}</Text>
        </Pressable>
      ) : null}
    </Animated.View>
  );
}

const s = StyleSheet.create({
  toast: {
    alignSelf: "center",
    flexDirection: "row",
    alignItems: "center",
    gap: espaco["space-3"],
    paddingVertical: espaco["space-3"],
    paddingLeft: espaco["space-4"],
    paddingRight: espaco["space-3"],
    borderRadius: raio["radius-pill"],
  },
  texto: { flexShrink: 1 },
  acao: {
    minHeight: medida.acaoToast,
    justifyContent: "center",
    paddingHorizontal: espaco["space-3"],
    borderRadius: raio["radius-pill"],
  },
});
