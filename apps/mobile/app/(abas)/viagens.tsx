import { TelaProvisoria } from "@/componentes/TelaProvisoria";

export default function Viagens() {
  return (
    <TelaProvisoria
      titulo="Suas viagens"
      rota="/viagens"
      historias={["HU04", "HU06"]}
      proximas={[
        { rotulo: "Nova viagem", href: "/viagens/nova" },
        { rotulo: "Abrir viagem de exemplo", href: "/viagens/demo/paradas" },
      ]}
    />
  );
}
