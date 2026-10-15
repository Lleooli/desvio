import { TelaProvisoria } from "@/componentes/TelaProvisoria";

// Login com Google, Apple ou link por e-mail (Supabase Auth).
export default function Entrar() {
  return (
    <TelaProvisoria
      titulo="Entre para guardar suas viagens"
      rota="/entrar"
      historias={["HU01"]}
      proximas={[
        { rotulo: "Primeiro login → triagem", href: "/triagem" },
        { rotulo: "Já fiz a triagem → viagens", href: "/viagens" },
      ]}
    />
  );
}
