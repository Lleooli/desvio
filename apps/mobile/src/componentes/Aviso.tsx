import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { espaco, estiloTexto, useCores } from "@/tema";
import { Button } from "./Button";

type Props = {
  /** Frase curta que diz o que aconteceu e o que fazer. */
  mensagem: string;
  /** Rótulo do botão, curto: "Tentar de novo". */
  acao: string;
  onAcao: () => void;
};

/** Tela inteira com uma mensagem e uma ação: erro de rede, viagem que falta, sessão vencida. */
export function Aviso({ mensagem, acao, onAcao }: Props) {
  const { c } = useCores();
  return (
    <SafeAreaView style={[s.tela, { backgroundColor: c["surface-100"] }]}>
      <View style={s.conteudo} accessibilityRole="alert">
        <Text style={[estiloTexto("body"), s.texto, { color: c.ink }]}>{mensagem}</Text>
        <Button onPress={onAcao}>{acao}</Button>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  conteudo: { flex: 1, justifyContent: "center", alignItems: "center", padding: espaco["space-6"], gap: espaco["space-4"] },
  texto: { textAlign: "center" },
});
