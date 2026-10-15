import { TelaProvisoria } from "@/componentes/TelaProvisoria";

export default function Escalas() {
  return (
    <TelaProvisoria
      titulo="Onde você vai parar?"
      rota="/viagens/nova/escalas"
      historias={["HU06"]}
      proximas={[{ rotulo: "Buscar lugares", href: "/viagens/demo/carregando" }]}
    />
  );
}
