import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { espaco, estiloTexto, medida, raio, useCores } from "@/tema";
import { FundoCeu, type VarianteCeu } from "./Ceu";
import { useFoco } from "./foco";

type Props = {
  cidade: string;
  uf?: string;
  dias?: number;
  foto?: string | null;
  /** Céu de fundo quando não há foto. */
  variante?: VarianteCeu;
  selecionada?: boolean;
  onPress?: () => void;
};

// Os tamanhos de texto da janela ficam entre os estilos do DS (.dv-janela__nome e
// .dv-janela__dias no bundle); o letter-spacing segue a mesma proporção em em.
const nomeTitulo = estiloTexto("title");
const estiloNome = {
  ...nomeTitulo,
  fontSize: medida.janelaNome,
  lineHeight: medida.janelaNomeLinha,
  letterSpacing: ((nomeTitulo.letterSpacing ?? 0) / (nomeTitulo.fontSize ?? 1)) * medida.janelaNome,
};
const estiloDias = {
  ...estiloTexto("km"),
  fontSize: medida.janelaDias,
  lineHeight: medida.janelaDiasLinha,
  letterSpacing: 0.04 * medida.janelaDias,
};

/**
 * Cidade do modo avião em formato de janelinha de avião (topo em pílula, base em
 * arco). Use numa fileira rolável horizontal, com space-3 entre as janelas.
 */
export function JanelaCidade({ cidade, uf, dias, foto, variante = "faixa", selecionada = false, onPress }: Props) {
  const { c, sombra } = useCores();
  const foco = useFoco();
  const textoDias = dias != null ? `${dias} ${dias === 1 ? "dia" : "dias"}` : null;
  const leitura = [cidade, uf, textoDias].filter(Boolean).join(", ");

  return (
    <Pressable
      onPress={onPress}
      {...foco.eventos}
      accessibilityRole="button"
      accessibilityLabel={leitura}
      aria-selected={selecionada}
      style={[s.janela, foco.estilo]}
    >
      {({ pressed }) => (
        <>
          <View
            style={[
              s.moldura,
              { backgroundColor: selecionada ? c.faixa : c["surface-200"], boxShadow: sombra["shadow-1"] },
              pressed && { transform: [{ scale: medida.pressionado }] },
            ]}
          >
            <View style={s.vidro}>
              {foto ? (
                <Image source={{ uri: foto }} resizeMode="cover" style={StyleSheet.absoluteFill} />
              ) : (
                <FundoCeu variante={variante} />
              )}
              {textoDias ? (
                <View style={s.diasLinha}>
                  <Text style={[estiloDias, s.dias, { backgroundColor: c.vidro, color: c.ink }]}>{textoDias}</Text>
                </View>
              ) : null}
            </View>
          </View>
          <View>
            <Text style={[estiloNome, { color: c.ink }]}>{cidade}</Text>
            {uf ? <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>{uf}</Text> : null}
          </View>
        </>
      )}
    </Pressable>
  );
}

const s = StyleSheet.create({
  janela: { width: medida.janelaLargura, gap: espaco["space-2"] },
  moldura: {
    aspectRatio: 3 / 4,
    padding: medida.janelaMoldura,
    borderTopLeftRadius: raio["radius-pill"],
    borderTopRightRadius: raio["radius-pill"],
    borderBottomLeftRadius: raio["radius-arco"],
    borderBottomRightRadius: raio["radius-arco"],
  },
  vidro: {
    flex: 1,
    overflow: "hidden",
    borderTopLeftRadius: raio["radius-pill"],
    borderTopRightRadius: raio["radius-pill"],
    borderBottomLeftRadius: raio["radius-arco"] - medida.janelaMoldura,
    borderBottomRightRadius: raio["radius-arco"] - medida.janelaMoldura,
  },
  diasLinha: { position: "absolute", left: 0, right: 0, bottom: medida.janelaDiasBase, alignItems: "center" },
  // Sem o blur de 12px do vidro no web: o React Native não tem backdrop-filter.
  dias: {
    paddingVertical: medida.janelaDiasRespiro,
    paddingHorizontal: espaco["space-2"],
    borderRadius: raio["radius-pill"],
    overflow: "hidden",
    textTransform: "uppercase",
  },
});
