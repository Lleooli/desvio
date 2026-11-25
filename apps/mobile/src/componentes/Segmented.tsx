import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, useCores } from "@/tema";
import { useFoco } from "./foco";
import { Icon, type IconName } from "./Icon";

type Opcao<T> = { valor: T; label: string; icon?: IconName };

type Props<T extends string | number> = {
  /** De duas a quatro opções; mais que isso, use Chips de filtro. */
  opcoes: Opcao<T>[];
  /** Controlado: passe `valor` e `onChange`. Sem `valor`, o estado fica no componente a partir de `padrao`. */
  valor?: T;
  padrao?: T;
  onChange?: (valor: T) => void;
  /** Nome do grupo para o leitor de tela. */
  rotulo: string;
  block?: boolean;
};

/** Escolha entre duas a quatro opções exclusivas, sempre visíveis. */
export function Segmented<T extends string | number>({ opcoes, valor, padrao, onChange, rotulo, block = false }: Props<T>) {
  const { c } = useCores();
  const [interno, setInterno] = useState<T | undefined>(padrao ?? opcoes[0]?.valor);
  const atual = valor ?? interno;

  function escolher(v: T) {
    if (valor === undefined) setInterno(v);
    onChange?.(v);
  }

  return (
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel={rotulo}
      style={[s.trilho, { backgroundColor: c["surface-300"] }, block ? s.block : s.inline]}
    >
      {opcoes.map((o) => (
        <OpcaoSegmented key={String(o.valor)} opcao={o} ativa={o.valor === atual} onPress={() => escolher(o.valor)} />
      ))}
    </View>
  );
}

function OpcaoSegmented<T>({ opcao, ativa, onPress }: { opcao: Opcao<T>; ativa: boolean; onPress: () => void }) {
  const { c, sombra, tema } = useCores();
  const foco = useFoco();
  const cor = ativa ? c.ink : c["ink-muted"];
  // No escuro o surface-200 é mais escuro que o trilho (surface-300) e a sombra some no fundo:
  // sem o contorno, a opção escolhida quase não aparece.
  const contorno = ativa && tema === "dark" ? { borderWidth: 1, borderColor: c["ink-muted"] } : null;
  return (
    <Pressable
      onPress={onPress}
      {...foco.eventos}
      // A opção tem 44px; o hitSlop completa os 48px de alvo de toque.
      hitSlop={(espaco.touch - medida.opcaoSegmented) / 2}
      accessibilityRole="radio"
      accessibilityLabel={opcao.label}
      aria-checked={ativa}
      style={[s.opcao, ativa && { backgroundColor: c["surface-200"], boxShadow: sombra["shadow-1"] }, contorno, foco.estilo]}
    >
      {opcao.icon ? <Icon name={opcao.icon} size={tamanhoIcone.padrao} color={cor} /> : null}
      <Text style={[estiloTexto("button"), { color: cor }]}>{opcao.label}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  trilho: { flexDirection: "row", gap: espaco["space-1"], padding: espaco["space-1"], borderRadius: raio["radius-pill"] },
  inline: { alignSelf: "flex-start" },
  block: { alignSelf: "stretch" },
  opcao: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: espaco["space-2"],
    minHeight: medida.opcaoSegmented,
    paddingHorizontal: espaco["space-4"],
    borderRadius: raio["radius-pill"],
  },
});
