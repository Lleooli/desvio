import { TelaProvisoria } from "@/componentes/TelaProvisoria";

export default function Perfil() {
  return (
    <TelaProvisoria
      titulo="O que você curte"
      rota="/perfil"
      historias={["HU03", "HU16", "HU17", "HU18", "HU19"]}
      proximas={[{ rotulo: "Refazer as perguntas", href: "/triagem" }]}
    />
  );
}
