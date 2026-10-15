import { Link, type Href } from "expo-router";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { espaco, fontes, raio, useCores } from "@/tema";

type Props = {
  titulo: string;
  rota: string;
  /** Histórias de usuário do PRD que esta tela atende. */
  historias: string[];
  /** Para onde a tela leva, para navegar enquanto ela não existe de verdade. */
  proximas?: { rotulo: string; href: Href }[];
};

/**
 * Tela provisória: mostra a rota e as histórias que ela atende.
 * Substitua pelo layout do canvas de rotas (docs/rotas.md) ao implementar.
 */
export function TelaProvisoria({ titulo, rota, historias, proximas = [] }: Props) {
  const { c } = useCores();
  return (
    <SafeAreaView style={[s.tela, { backgroundColor: c["surface-100"] }]}>
      <ScrollView contentContainerStyle={s.conteudo}>
        <Text style={[s.rota, { color: c["ink-muted"] }]}>{rota}</Text>
        <Text style={[s.titulo, { color: c.ink }]}>{titulo}</Text>
        <Text style={[s.texto, { color: c["ink-muted"] }]}>Histórias: {historias.join(", ")}</Text>
        <View style={s.links}>
          {proximas.map((p) => (
            <Link key={p.rotulo} href={p.href} style={[s.botao, { backgroundColor: c.placa, color: c["on-placa"] }]}>
              {p.rotulo}
            </Link>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  conteudo: { padding: espaco["space-4"], paddingTop: espaco["space-8"], gap: espaco["space-3"] },
  rota: { fontFamily: fontes.placa, fontSize: 16, letterSpacing: 0.6, textTransform: "uppercase" },
  titulo: { fontFamily: fontes.display, fontSize: 40, lineHeight: 40, letterSpacing: -1.4 },
  texto: { fontFamily: fontes.sans, fontSize: 15, lineHeight: 22 },
  links: { gap: espaco["space-3"], marginTop: espaco["space-6"] },
  botao: {
    overflow: "hidden",
    minHeight: espaco["button-h"],
    lineHeight: espaco["button-h"],
    borderRadius: raio["radius-pill"],
    textAlign: "center",
    fontFamily: fontes.sansForte,
    fontSize: 16,
  },
});
