import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, useCores } from "@/tema";
import { useFoco } from "./foco";
import { Icon, type IconName } from "./Icon";

/** As quatro áreas do app, sempre nesta ordem. O id é o nome da rota em app/(abas). */
export const areas = [
  { id: "viagens", label: "Viagens", icon: "suitcase" },
  { id: "descobrir", label: "Descobrir", icon: "compass" },
  { id: "roteiro", label: "Roteiro", icon: "route" },
  { id: "perfil", label: "Perfil", icon: "user" },
] as const satisfies readonly { id: string; label: string; icon: IconName }[];

export type Area = (typeof areas)[number]["id"];

type Props = {
  ativo: Area;
  onChange: (area: Area) => void;
};

/** Barra fixa no rodapé com as quatro áreas; respeita a área segura do iPhone. */
export function BottomNav({ ativo, onChange }: Props) {
  const { c, sombra } = useCores();
  const { bottom } = useSafeAreaInsets();
  return (
    <View
      accessibilityRole="tablist"
      accessibilityLabel="Navegação principal"
      style={[
        s.barra,
        { backgroundColor: c["surface-200"], boxShadow: sombra["shadow-sheet"], paddingBottom: espaco["space-1"] + bottom },
      ]}
    >
      {areas.map((a) => (
        <ItemNav key={a.id} label={a.label} icon={a.icon} atual={a.id === ativo} onPress={() => onChange(a.id)} />
      ))}
    </View>
  );
}

type ItemProps = { label: string; icon: IconName; atual: boolean; onPress: () => void };

function ItemNav({ label, icon, atual, onPress }: ItemProps) {
  const { c } = useCores();
  const foco = useFoco();
  const cor = atual ? c.placa : c["ink-muted"];
  return (
    <Pressable
      onPress={onPress}
      {...foco.eventos}
      accessibilityRole="tab"
      accessibilityLabel={label}
      aria-selected={atual}
      style={[s.item, foco.estilo]}
    >
      <View style={[s.pilula, atual && { backgroundColor: c["surface-300"] }]}>
        <Icon name={icon} size={tamanhoIcone.nav} color={cor} />
      </View>
      <Text style={[estiloTexto("label"), { color: cor }]}>{label}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  barra: {
    flexDirection: "row",
    paddingTop: espaco["space-1"],
    paddingHorizontal: espaco["space-2"],
  },
  item: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: espaco["space-1"],
    minHeight: medida.itemNav,
    borderRadius: raio["radius-md"],
  },
  pilula: {
    width: medida.pilulaNavLargura,
    height: medida.pilulaNavAltura,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: raio["radius-pill"],
  },
});
