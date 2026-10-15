import { useLocalSearchParams } from "expo-router";
import { TelaProvisoria } from "@/componentes/TelaProvisoria";

export default function Roteiro() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return (
    <TelaProvisoria
      titulo="Seu roteiro está pronto"
      rota={`/viagens/${id}/roteiro`}
      historias={["HU13", "HU14", "HU15"]}
      proximas={[{ rotulo: "Editar", href: { pathname: "/viagens/[id]/paradas", params: { id } } }]}
    />
  );
}
