import { useLocalSearchParams } from "expo-router";
import { TelaProvisoria } from "@/componentes/TelaProvisoria";

// Mostra as etapas da coleta (POST /viagem no coletor) e avisa por push.
export default function Carregando() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return (
    <TelaProvisoria
      titulo="Procurando paradas no caminho"
      rota={`/viagens/${id}/carregando`}
      historias={["HU07"]}
      proximas={[{ rotulo: "Ver as paradas", href: { pathname: "/viagens/[id]/paradas", params: { id } } }]}
    />
  );
}
