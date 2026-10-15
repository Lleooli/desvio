import { TelaProvisoria } from "@/componentes/TelaProvisoria";

// Carro: origem, destino, intervalo e categorias. Avião: segue para /viagens/nova/escalas.
export default function NovaViagem() {
  return (
    <TelaProvisoria
      titulo="Para onde a estrada te leva?"
      rota="/viagens/nova"
      historias={["HU04", "HU05"]}
      proximas={[
        { rotulo: "Buscar paradas (carro)", href: "/viagens/demo/carregando" },
        { rotulo: "Continuar para as escalas (avião)", href: "/viagens/nova/escalas" },
      ]}
    />
  );
}
