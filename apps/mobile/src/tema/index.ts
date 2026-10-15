import { useColorScheme } from "react-native";
import { cores, espaco, raio, tipografia, type Cor, type Tema } from "./tokens.gerado";

export { espaco, raio, tipografia };
export type { Cor, Tema };

/** Fontes carregadas em app/_layout.tsx (pacotes @expo-google-fonts). */
export const fontes = {
  display: "BricolageGrotesque_700Bold",
  placa: "BarlowCondensed_600SemiBold",
  placaForte: "BarlowCondensed_700Bold",
  sans: "Barlow_400Regular",
  sansForte: "Barlow_600SemiBold",
} as const;

/** Cores do tema atual (segue o sistema; a escolha do perfil entra aqui depois). */
export function useCores() {
  const esquema = useColorScheme();
  const tema: Tema = esquema === "dark" ? "dark" : "light";
  return { tema, c: cores[tema] };
}
