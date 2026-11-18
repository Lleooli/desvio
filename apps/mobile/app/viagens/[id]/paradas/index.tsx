import { useLocalSearchParams } from "expo-router";
import { TelaProvisoria } from "@/componentes/TelaProvisoria";
import { useMarcarViagemAtiva } from "@/viagemAtiva";

export default function Paradas() {
  const { id } = useLocalSearchParams<{ id: string }>();
  useMarcarViagemAtiva(id);
  return (
    <TelaProvisoria
      titulo="Escolha suas paradas"
      rota={`/viagens/${id}/paradas`}
      historias={["HU08"]}
      proximas={[
        { rotulo: "Abrir swipe de Curitiba", href: { pathname: "/viagens/[id]/paradas/[paradaId]", params: { id, paradaId: "2" } } },
        { rotulo: "Montar roteiro", href: { pathname: "/viagens/[id]/roteiro", params: { id } } },
      ]}
    />
  );
}
