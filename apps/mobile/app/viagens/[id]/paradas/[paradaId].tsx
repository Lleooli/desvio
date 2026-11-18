import { useLocalSearchParams } from "expo-router";
import { TelaProvisoria } from "@/componentes/TelaProvisoria";
import { useMarcarViagemAtiva } from "@/viagemAtiva";

// O swipe: SwipeCard + SwipeActions (design system Desvio), gestos com Gesture Handler e Reanimated.
export default function Swipe() {
  const { id, paradaId } = useLocalSearchParams<{ id: string; paradaId: string }>();
  useMarcarViagemAtiva(id);
  return (
    <TelaProvisoria
      titulo="Swipe da parada"
      rota={`/viagens/${id}/paradas/${paradaId}`}
      historias={["HU09", "HU10", "HU12", "HU18"]}
      proximas={[
        { rotulo: "Ver detalhes do lugar", href: { pathname: "/lugares/[lugarId]", params: { lugarId: "osm:node-1" } } },
        { rotulo: "Pronto", href: { pathname: "/viagens/[id]/paradas", params: { id } } },
      ]}
    />
  );
}
