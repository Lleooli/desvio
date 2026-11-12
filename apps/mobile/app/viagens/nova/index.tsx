import { TelaProvisoria } from "@/componentes/TelaProvisoria";

// Veículo (carro, moto ou bicicleta), origem, destino, intervalo escolhido pela pessoa e categorias.
export default function NovaViagem() {
  return (
    <TelaProvisoria
      titulo="Para onde a estrada te leva?"
      rota="/viagens/nova"
      historias={["HU04", "HU05"]}
      proximas={[
        { rotulo: "Buscar paradas", href: "/viagens/demo/carregando" },
      ]}
    />
  );
}
