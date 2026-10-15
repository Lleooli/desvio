import { TelaProvisoria } from "@/componentes/TelaProvisoria";

// Conversa com a IA, no máximo 5 perguntas; a resposta vira o perfil de gosto.
export default function Triagem() {
  return (
    <TelaProvisoria
      titulo="Conhecendo você"
      rota="/triagem"
      historias={["HU02", "HU03"]}
      proximas={[
        { rotulo: "Planejar minha primeira viagem", href: "/viagens/nova" },
        { rotulo: "Pular", href: "/viagens" },
      ]}
    />
  );
}
