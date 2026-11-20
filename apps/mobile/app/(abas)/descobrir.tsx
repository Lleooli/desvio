import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { NaViagemAtiva } from "@/componentes/NaViagemAtiva";
import { ParadasDaViagem } from "@/componentes/ParadasDaViagem";
import { useCores } from "@/tema";

// Aba Descobrir: as paradas da viagem ativa (mesmo conteúdo de /viagens/:id/paradas).
export default function Descobrir() {
  const { c } = useCores();
  const margens = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, paddingTop: margens.top, backgroundColor: c["surface-100"] }}>
      <NaViagemAtiva>{(viagem, recarregar) => <ParadasDaViagem viagem={viagem} recarregar={recarregar} />}</NaViagemAtiva>
    </View>
  );
}
