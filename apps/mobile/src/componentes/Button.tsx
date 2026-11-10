import { Pressable, StyleSheet, Text, View } from "react-native";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, tipografia, useCores } from "@/tema";
import { useFoco } from "./foco";
import { Icon, type IconName } from "./Icon";

type Props = {
  /** Verbo no infinitivo, curto: "Montar roteiro". */
  children: string;
  onPress: () => void;
  /** primary = placa; secondary = contorno ink; ghost = só texto placa; favorito = faixa com brilho. */
  variant?: "primary" | "secondary" | "ghost" | "favorito";
  size?: "md" | "sm";
  icon?: IconName;
  /** Ocupa a largura toda (CTAs no rodapé da tela). */
  block?: boolean;
  disabled?: boolean;
};

/** Botão de ação para tudo que não é a decisão de swipe (essa é o SwipeActions). */
export function Button({ children, onPress, variant = "primary", size = "md", icon, block = false, disabled = false }: Props) {
  const { c, sombra } = useCores();
  const foco = useFoco();
  const sm = size === "sm";

  const fundo = { primary: c.placa, secondary: "transparent", ghost: "transparent", favorito: c.faixa }[variant];
  const texto = { primary: c["on-placa"], secondary: c.ink, ghost: c.placa, favorito: c["on-faixa"] }[variant];
  const altura = sm ? medida.botaoSm : espaco["button-h"];
  // O sm tem 40px; o hitSlop completa o alvo de toque de 48px.
  const folga = (espaco.touch - altura) / 2;

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      {...foco.eventos}
      hitSlop={folga > 0 ? folga : undefined}
      accessibilityRole="button"
      accessibilityLabel={children}
      accessibilityState={{ disabled }}
      style={({ pressed }) => [
        s.base,
        {
          minHeight: altura,
          paddingHorizontal: variant === "ghost" ? espaco["space-3"] : sm ? espaco["space-4"] : espaco["space-6"],
          backgroundColor: fundo,
          borderColor: variant === "secondary" ? c.ink : "transparent",
        },
        block && s.block,
        variant === "favorito" && !disabled && { boxShadow: sombra["shadow-favorito"] },
        foco.estilo,
        pressed && { transform: [{ scale: medida.pressionado }] },
        disabled && { opacity: medida.desabilitado },
      ]}
    >
      <View style={s.conteudo}>
        {icon ? <Icon name={icon} size={sm ? tamanhoIcone.botaoSm : tamanhoIcone.padrao} color={texto} /> : null}
        <Text style={[estiloTexto("button"), sm && { fontSize: tipografia["body-s"].tamanho }, { color: texto }]}>
          {children}
        </Text>
      </View>
    </Pressable>
  );
}

const s = StyleSheet.create({
  base: {
    alignSelf: "flex-start",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: raio["radius-pill"],
    borderWidth: medida.borda,
  },
  block: { alignSelf: "stretch" },
  conteudo: { flexDirection: "row", alignItems: "center", gap: espaco["space-2"] },
});
