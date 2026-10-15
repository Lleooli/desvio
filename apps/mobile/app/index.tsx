import { Redirect } from "expo-router";

// Sem sessão: boas-vindas. Com sessão (a ligar com o Supabase): /viagens.
export default function Inicio() {
  return <Redirect href="/boas-vindas" />;
}
