import { Redirect } from "expo-router";
import { useSessao } from "@/sessao";

// Sem sessão: boas-vindas. Com sessão guardada no aparelho: Minhas viagens.
export default function Inicio() {
  const { sessao, carregou } = useSessao();
  if (!carregou) return null; // um instante, enquanto o aparelho devolve a sessão
  return <Redirect href={sessao ? "/viagens" : "/boas-vindas"} />;
}
