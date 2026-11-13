import { Text } from "react-native";
import { useCores } from "@/tema";

type Props = {
  /** A palavra (ou duas) do título que carrega a ação. */
  children: string;
};

/**
 * Marca-texto amarelo atrás de uma palavra de título em display-xl ou title.
 * Use dentro do <Text> do título: "Escolha suas <Destaque>paradas</Destaque>".
 *
 * O React Native não pinta só uma faixa da altura da linha (o linear-gradient do
 * bundle), então no claro o halo cobre a palavra inteira. No escuro vira um traço
 * sob a palavra, para o texto claro continuar legível; o Android desenha esse traço
 * na cor do texto, porque ignora textDecorationColor.
 */
export function Destaque({ children }: Props) {
  const { tema, c } = useCores();
  const estilo =
    tema === "dark"
      ? { textDecorationLine: "underline" as const, textDecorationColor: c.faixa }
      : { backgroundColor: c["halo-foco"] };
  return <Text style={estilo}>{children}</Text>;
}
