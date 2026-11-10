import { useState } from "react";
import { StyleSheet, Text, TextInput, View, type TextInputProps } from "react-native";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, useCores } from "@/tema";
import { Icon, type IconName } from "./Icon";

type Props = Omit<TextInputProps, "style" | "placeholderTextColor"> & {
  /** Sempre visível, em forma de pergunta: "De onde você sai?". */
  label: string;
  icon?: IconName;
  hint?: string;
  /** Diz o que fazer ("Confira a grafia"); toma o lugar da dica. */
  erro?: string;
};

/** Campo de texto com rótulo, ícone opcional, dica e erro. */
export function TextField({ label, icon, hint, erro, onFocus, onBlur, ...input }: Props) {
  const { c } = useCores();
  const [focado, setFocado] = useState(false);
  const mensagem = erro ?? hint;

  const borda = erro ? c.perigo : focado ? c.ink : c["ink-muted"];
  const corIcone = focado ? c.ink : c["ink-muted"];

  return (
    <View style={s.campo}>
      <Text style={[estiloTexto("body-strong"), { color: c.ink }]}>{label}</Text>
      <View
        style={[
          s.caixa,
          { backgroundColor: c["surface-200"], borderColor: borda },
          focado && { boxShadow: `0 0 0 ${medida.haloCampo}px ${c["halo-foco"]}` },
        ]}
      >
        {icon ? <Icon name={icon} size={tamanhoIcone.padrao} color={corIcone} /> : null}
        <TextInput
          {...input}
          accessibilityLabel={label}
          accessibilityHint={mensagem}
          aria-invalid={!!erro}
          placeholderTextColor={c["ink-muted"]}
          onFocus={(e) => {
            setFocado(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocado(false);
            onBlur?.(e);
          }}
          style={[estiloTexto("body"), s.input, { color: c.ink }]}
        />
      </View>
      {mensagem ? (
        <Text style={[estiloTexto("body-s"), { color: erro ? c.perigo : c["ink-muted"] }]}>{mensagem}</Text>
      ) : null}
    </View>
  );
}

const s = StyleSheet.create({
  campo: { gap: espaco["space-2"] },
  caixa: {
    flexDirection: "row",
    alignItems: "center",
    gap: espaco["space-2"],
    minHeight: espaco["button-h"],
    paddingHorizontal: espaco["space-4"],
    borderRadius: raio["radius-md"],
    borderWidth: medida.borda,
  },
  input: { flex: 1, minWidth: 0, paddingVertical: espaco["space-3"] },
});
