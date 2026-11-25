import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useCores, type Cor } from "@/tema";

/**
 * Fundo atrás da barra de status do celular. Com o app de ponta a ponta (edge-to-edge), o
 * conteúdo de uma tela que rola passaria por baixo do relógio e dos ícones; esta faixa, na
 * cor da tela, fica por cima dele. Ponha como último filho da tela, irmã do ScrollView.
 */
export function FaixaDoStatus({ cor = "surface-100" }: { cor?: Cor }) {
  const { c } = useCores();
  const { top } = useSafeAreaInsets();
  return <View aria-hidden pointerEvents="none" style={[s.faixa, { height: top, backgroundColor: c[cor] }]} />;
}

const s = StyleSheet.create({
  faixa: { position: "absolute", top: 0, left: 0, right: 0 },
});
