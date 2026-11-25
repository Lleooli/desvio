import { useLocalSearchParams } from "expo-router";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { NaViagemAtiva } from "@/componentes/NaViagemAtiva";
import { ParadasDaViagem } from "@/componentes/ParadasDaViagem";
import { useCores } from "@/tema";
import { useMarcarViagemAtiva } from "@/viagemAtiva";

/** As paradas da viagem na ordem da estrada; o toque numa parada abre o swipe dela (HU08). */
export default function Paradas() {
  const { id } = useLocalSearchParams<{ id: string }>();
  useMarcarViagemAtiva(id);
  const { c } = useCores();
  const margens = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, paddingTop: margens.top, paddingBottom: margens.bottom, backgroundColor: c["surface-100"] }}>
      <NaViagemAtiva id={id}>{(viagem, recarregar) => <ParadasDaViagem viagem={viagem} recarregar={recarregar} />}</NaViagemAtiva>
    </View>
  );
}
