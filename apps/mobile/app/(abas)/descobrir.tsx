import { TelaProvisoria } from "@/componentes/TelaProvisoria";

// Aba Descobrir: as paradas da viagem ativa (mesmo conteúdo de /viagens/:id/paradas).
export default function Descobrir() {
  return (
    <TelaProvisoria
      titulo="Escolha suas paradas"
      rota="aba Descobrir → /viagens/:id/paradas"
      historias={["HU08"]}
      proximas={[{ rotulo: "Abrir swipe de Curitiba", href: "/viagens/demo/paradas/2" }]}
    />
  );
}
