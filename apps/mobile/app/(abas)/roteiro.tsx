import { TelaProvisoria } from "@/componentes/TelaProvisoria";

// Aba Roteiro: o roteiro da viagem ativa (mesmo conteúdo de /viagens/:id/roteiro).
export default function AbaRoteiro() {
  return (
    <TelaProvisoria
      titulo="Seu roteiro está pronto"
      rota="aba Roteiro → /viagens/:id/roteiro"
      historias={["HU13", "HU14", "HU15"]}
      proximas={[{ rotulo: "Editar paradas", href: "/viagens/demo/paradas" }]}
    />
  );
}
