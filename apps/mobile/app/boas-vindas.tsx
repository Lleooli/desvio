import { useRouter } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Button } from "@/componentes/Button";
import { Ceu } from "@/componentes/Ceu";
import { Destaque } from "@/componentes/Destaque";
import { Estrada } from "@/componentes/Estrada";
import { espaco, estiloTexto, useCores } from "@/tema";

const CIDADES = ["Alegrete", "Lages", "Curitiba", "Belo Horizonte", "Vitória da Conquista"];

/** Primeira tela sem sessão: o céu com a Estrada e o convite para entrar (canvas BoasVindas). */
export default function BoasVindas() {
  const { c } = useCores();
  const router = useRouter();
  const margens = useSafeAreaInsets();

  return (
    <View style={[s.tela, { backgroundColor: c["surface-100"] }]}>
      <Ceu serra style={s.ceu}>
        <View style={{ paddingTop: margens.top }}>
          <Text style={[estiloTexto("estrada"), s.marca, { color: c.ink }]}>Desvio</Text>
          <View style={s.estrada}>
            <Estrada cidades={CIDADES} variante="subida" />
          </View>
          <Text accessibilityRole="header" style={[estiloTexto("display-xl"), { color: c.ink }]}>
            Cada parada, escolhida a <Destaque>dedo</Destaque>
          </Text>
          <Text style={[estiloTexto("body"), s.texto, { color: c["ink-muted"] }]}>
            Diga para onde vai. A gente acha mirantes, restaurantes e postos no caminho, e você escolhe deslizando.
          </Text>
        </View>
      </Ceu>
      <View style={[s.acoes, { paddingBottom: margens.bottom + espaco["space-8"] }]}>
        <Button block onPress={() => router.push("/entrar")}>
          Começar
        </Button>
        <Button block variant="ghost" onPress={() => router.push("/entrar")}>
          Já tenho conta
        </Button>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  ceu: { flex: 1 },
  marca: { textTransform: "uppercase" },
  estrada: { marginTop: espaco["space-8"], marginBottom: espaco["space-6"], marginHorizontal: -espaco["space-4"] },
  texto: { marginTop: espaco["space-4"] },
  acoes: { gap: espaco["space-2"], paddingTop: espaco["space-4"], paddingHorizontal: espaco["space-4"] },
});
