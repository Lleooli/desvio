import { router, useLocalSearchParams } from "expo-router";
import { TelaProvisoria } from "@/componentes/TelaProvisoria";

// Folha de detalhe do lugar (abre como modal sobre o swipe).
export default function Lugar() {
  const { lugarId } = useLocalSearchParams<{ lugarId: string }>();
  return (
    <TelaProvisoria
      titulo="Detalhe do lugar"
      rota={`/lugares/${lugarId}`}
      historias={["HU11"]}
      proximas={router.canGoBack() ? [] : [{ rotulo: "Voltar às viagens", href: "/viagens" }]}
    />
  );
}
