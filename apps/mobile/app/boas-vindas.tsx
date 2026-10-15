import { TelaProvisoria } from "@/componentes/TelaProvisoria";

export default function BoasVindas() {
  return (
    <TelaProvisoria
      titulo="Cada parada, escolhida a dedo"
      rota="/boas-vindas"
      historias={["HU01"]}
      proximas={[{ rotulo: "Começar", href: "/entrar" }]}
    />
  );
}
