import { useLocalSearchParams } from "expo-router";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { NaViagemAtiva } from "@/componentes/NaViagemAtiva";
import { SwipeDaParada } from "@/componentes/SwipeDaParada";
import { useCores } from "@/tema";
import { useMarcarViagemAtiva } from "@/viagemAtiva";

/** O swipe de uma parada (HU09, HU10). Fica fora das abas, então a BottomNav não aparece. */
export default function Swipe() {
  const { id, paradaId } = useLocalSearchParams<{ id: string; paradaId: string }>();
  useMarcarViagemAtiva(id);
  const { c } = useCores();
  const margens = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, paddingTop: margens.top, paddingBottom: margens.bottom, backgroundColor: c["surface-100"] }}>
      <NaViagemAtiva id={id}>{(viagem) => <SwipeDaParada viagem={viagem} ordem={Number(paradaId)} />}</NaViagemAtiva>
    </View>
  );
}
