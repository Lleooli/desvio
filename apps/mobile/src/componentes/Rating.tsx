import { StyleSheet, Text, View } from "react-native";
import { espaco, estiloTexto, fontes, tamanhoIcone, useCores } from "@/tema";
import { Icon } from "./Icon";

type Props = {
  /** 0 a 5. Sem nota (lugar só do OpenStreetMap), não renderiza nada. */
  nota?: number | null;
  avaliacoes?: number | null;
  /** Sobre a foto do card: tudo em on-scrim. */
  onPhoto?: boolean;
};

/** Formata no padrão brasileiro: 4,7 e 1.834. */
export function numero(n: number, casas = 0): string {
  return n.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

/** Nota do Google Maps com a contagem de avaliações: "4,7 (1.834)". */
export function Rating({ nota, avaliacoes, onPhoto = false }: Props) {
  const { c } = useCores();
  if (nota == null) return null;

  const texto = numero(nota, 1);
  const total = avaliacoes != null ? numero(avaliacoes) : null;
  const corNota = onPhoto ? c["on-scrim"] : c.ink;
  const corTotal = onPhoto ? c["on-scrim"] : c["ink-muted"];

  return (
    <View
      accessible
      accessibilityLabel={`Nota ${texto}${total ? `, ${total} avaliações` : ""}`}
      style={s.linha}
    >
      <Icon name="star" filled size={tamanhoIcone.chip} color={onPhoto ? c["on-scrim"] : c.estrela} />
      <Text style={[estiloTexto("body-s"), s.nota, { color: corNota }]}>{texto}</Text>
      {total ? <Text style={[estiloTexto("body-s"), { color: corTotal }]}>({total})</Text> : null}
    </View>
  );
}

const s = StyleSheet.create({
  linha: { flexDirection: "row", alignItems: "center", gap: espaco["space-1"] },
  nota: { fontFamily: fontes.sansForte },
});
