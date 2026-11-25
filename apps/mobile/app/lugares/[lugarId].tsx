import { useLocalSearchParams } from "expo-router";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Aviso } from "@/componentes/Aviso";
import { FolhaDoLugar } from "@/componentes/FolhaDoLugar";
import { fecharFolhaDoLugar, folhaAberta } from "@/folhaDoLugar";
import { useCores } from "@/tema";

/** Folha de detalhe do lugar (HU11): abre como modal sobre o swipe e volta para ele ao fechar ou decidir. */
export default function Lugar() {
  const { lugarId } = useLocalSearchParams<{ lugarId: string }>();
  const { c } = useCores();
  const margens = useSafeAreaInsets();
  const folha = folhaAberta(lugarId);
  if (!folha) {
    return <Aviso mensagem="Abra o lugar pelo swipe da parada." acao="Voltar" onAcao={() => fecharFolhaDoLugar()} />;
  }
  return (
    <View style={{ flex: 1, paddingTop: margens.top, paddingBottom: margens.bottom, backgroundColor: c["surface-200"] }}>
      <FolhaDoLugar
        card={folha.card}
        onBora={() => fecharFolhaDoLugar("bora")}
        onPasso={() => fecharFolhaDoLugar("passo")}
        onFechar={() => fecharFolhaDoLugar()}
      />
    </View>
  );
}
