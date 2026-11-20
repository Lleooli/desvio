import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { NaViagemAtiva } from "@/componentes/NaViagemAtiva";
import { RoteiroDaViagem } from "@/componentes/RoteiroDaViagem";
import { useCores } from "@/tema";

// Aba Roteiro: o roteiro da viagem ativa (mesmo conteúdo de /viagens/:id/roteiro).
export default function AbaRoteiro() {
  const { c } = useCores();
  const margens = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, paddingTop: margens.top, backgroundColor: c["surface-100"] }}>
      <NaViagemAtiva>{(viagem) => <RoteiroDaViagem viagem={viagem} />}</NaViagemAtiva>
    </View>
  );
}
