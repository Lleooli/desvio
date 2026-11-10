import { Pressable, StyleSheet, Text, View } from "react-native";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, useCores } from "@/tema";
import { useFoco } from "./foco";
import { Icon, type IconName } from "./Icon";

/** As cinco categorias têm o mesmo visual: quem diferencia é o ícone e a palavra. */
export const categorias = {
  turismo: { label: "Turismo", icon: "camera" },
  restaurante: { label: "Restaurante", icon: "food" },
  posto: { label: "Posto", icon: "fuel" },
  natureza: { label: "Natureza", icon: "leaf" },
  hospedagem: { label: "Hospedagem", icon: "bed" },
} as const satisfies Record<string, { label: string; icon: IconName }>;

export type Categoria = keyof typeof categorias;

type Props = {
  /** Preenche rótulo e ícone. Sem ela, use `label` e `icon`. */
  categoria?: Categoria;
  label?: string;
  icon?: IconName;
  /** Com `onPress` vira filtro liga/desliga. */
  selected?: boolean;
  onPress?: () => void;
  /** Fundo em vidro para ficar legível sobre a foto do card. */
  onPhoto?: boolean;
};

/** Rótulo de categoria do lugar; com `onPress` vira filtro. */
export function Chip({ categoria, label, icon, selected = false, onPress, onPhoto = false }: Props) {
  const { c, sombra } = useCores();
  const foco = useFoco();
  const rotulo = label ?? (categoria ? categorias[categoria].label : "");
  const icone = icon ?? (categoria ? categorias[categoria].icon : undefined);
  const ativo = !!onPress && selected;

  const fundo = ativo ? c.ink : onPhoto ? c.vidro : c["surface-300"];
  const cor = ativo ? c["surface-100"] : c.ink;
  const conteudo = (
    <>
      {icone ? <Icon name={icone} size={tamanhoIcone.chip} color={cor} /> : null}
      <Text style={[estiloTexto("label"), s.texto, { color: cor }]}>{rotulo}</Text>
    </>
  );

  if (!onPress) {
    return <View style={[s.base, { minHeight: medida.chip, backgroundColor: fundo }]}>{conteudo}</View>;
  }

  return (
    <Pressable
      onPress={onPress}
      {...foco.eventos}
      // O filtro tem 42px; o hitSlop completa os 48px de alvo de toque.
      hitSlop={(espaco.touch - medida.chipFiltro) / 2}
      accessibilityRole="togglebutton"
      accessibilityLabel={rotulo}
      aria-checked={ativo}
      style={({ pressed }) => [
        s.base,
        { minHeight: medida.chipFiltro, paddingHorizontal: espaco["space-4"], backgroundColor: fundo },
        ativo && { boxShadow: sombra["shadow-1"] },
        foco.estilo,
        pressed && { transform: [{ scale: medida.pressionado }] },
      ]}
    >
      {conteudo}
    </Pressable>
  );
}

const s = StyleSheet.create({
  base: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: espaco["space-1"],
    paddingHorizontal: espaco["space-3"],
    borderRadius: raio["radius-pill"],
  },
  texto: { textTransform: "uppercase" },
});
