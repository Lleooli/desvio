import { useState } from "react";
import type { ViewStyle } from "react-native";
import { medida, useCores } from "@/tema";

/**
 * Contorno de foco do DS para controles que não são campo: 2px em `foco`, afastado 2px.
 * Espalhe `eventos` no Pressable e aplique `estilo` no style dele.
 */
export function useFoco() {
  const { c } = useCores();
  const [focado, setFocado] = useState(false);
  const eventos = { onFocus: () => setFocado(true), onBlur: () => setFocado(false) };
  const estilo: ViewStyle | false = focado && {
    outlineColor: c.foco,
    outlineStyle: "solid",
    outlineWidth: medida.foco,
    outlineOffset: medida.foco,
  };
  return { eventos, estilo };
}
