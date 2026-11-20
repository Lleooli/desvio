import { Redirect } from "expo-router";
import { useSessao } from "@/sessao";
import { useViagemAtiva } from "@/viagemAtiva";

// Sem sessão: boas-vindas. Com sessão e uma viagem aberta: a aba Descobrir, que leva à busca
// em andamento ou às paradas (reabrir o app volta à tela certa). Sem viagem: Minhas viagens.
export default function Inicio() {
  const { sessao, carregou } = useSessao();
  const ativa = useViagemAtiva();
  if (!carregou || (sessao && !ativa.carregou)) return null; // um instante, enquanto o aparelho responde
  if (!sessao) return <Redirect href="/boas-vindas" />;
  return <Redirect href={ativa.id ? "/descobrir" : "/viagens"} />;
}
