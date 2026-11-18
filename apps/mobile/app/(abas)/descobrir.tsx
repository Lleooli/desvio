import { NaViagemAtiva } from "@/componentes/NaViagemAtiva";
import { TelaProvisoria } from "@/componentes/TelaProvisoria";

// Aba Descobrir: as paradas da viagem ativa (mesmo conteúdo de /viagens/:id/paradas).
export default function Descobrir() {
  return (
    <NaViagemAtiva>
      {(viagem) => (
        <TelaProvisoria
          titulo="Escolha suas paradas"
          rota={`aba Descobrir → /viagens/${viagem.id}/paradas`}
          historias={["HU08"]}
          proximas={viagem.paradas.map((p) => ({
            rotulo: `Abrir swipe de ${p.nome}`,
            href: { pathname: "/viagens/[id]/paradas/[paradaId]", params: { id: viagem.id, paradaId: String(p.ordem) } },
          }))}
        />
      )}
    </NaViagemAtiva>
  );
}
