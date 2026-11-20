import { useLocalSearchParams } from "expo-router";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { NaViagemAtiva } from "@/componentes/NaViagemAtiva";
import { RoteiroDaViagem } from "@/componentes/RoteiroDaViagem";
import { useCores } from "@/tema";
import { useMarcarViagemAtiva } from "@/viagemAtiva";

/** O roteiro da viagem de carro, com os lugares de Bora na ordem do km (HU13). */
export default function Roteiro() {
  const { id } = useLocalSearchParams<{ id: string }>();
  useMarcarViagemAtiva(id);
  const { c } = useCores();
  const margens = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, paddingTop: margens.top, paddingBottom: margens.bottom, backgroundColor: c["surface-100"] }}>
      <NaViagemAtiva id={id}>{(viagem) => <RoteiroDaViagem viagem={viagem} />}</NaViagemAtiva>
    </View>
  );
}
