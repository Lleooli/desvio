import { Redirect, router } from "expo-router";
import type { ReactNode } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { obterViagem, type Viagem } from "@/api";
import { useCarregar } from "@/api/useCarregar";
import { useCores } from "@/tema";
import { esquecerViagemAtiva, useViagemAtiva } from "@/viagemAtiva";
import { Aviso } from "./Aviso";

type Props = {
  /** A viagem a carregar; sem ele, a viagem ativa (abas Descobrir e Roteiro). */
  id?: string;
  /** Recebe a viagem e `recarregar`, que busca de novo sem tirar a viagem da tela. */
  children: (viagem: Viagem, recarregar: () => void) => ReactNode;
};

/**
 * Carrega a viagem ativa (ou a do `id`) e só desenha `children` com ela.
 * Sem viagem aberta, leva para Minhas viagens; com erro, mostra a mensagem e Tentar de novo.
 * Viagem que não existe mais (ou é de outra conta) e sessão vencida não se resolvem tentando
 * de novo: esquece a viagem ativa e leva para Minhas viagens ou para o login.
 */
export function NaViagemAtiva({ id, children }: Props) {
  const { c } = useCores();
  const ativa = useViagemAtiva();
  const viagemId = id ?? ativa.id;
  const { dados, erro, tipoErro, carregando, tentarDeNovo } = useCarregar(viagemId, obterViagem);

  if (!id && ativa.carregou && !ativa.id) {
    return <Aviso mensagem="Você ainda não abriu nenhuma viagem." acao="Ver viagens" onAcao={() => router.navigate("/viagens")} />;
  }
  if (erro && (tipoErro === "nao-encontrado" || tipoErro === "sessao")) {
    const destino = tipoErro === "sessao" ? "/entrar" : "/viagens";
    const sair = () => {
      esquecerViagemAtiva();
      router.navigate(destino);
    };
    return <Aviso mensagem={erro} acao={tipoErro === "sessao" ? "Entrar" : "Ver viagens"} onAcao={sair} />;
  }
  if (erro) return <Aviso mensagem={erro} acao="Tentar de novo" onAcao={tentarDeNovo} />;
  // Recarregar a mesma viagem deixa a de antes na tela; trocar de viagem mostra o carregando.
  if (!dados || (carregando && dados.id !== viagemId)) {
    return (
      <View style={[s.centro, { backgroundColor: c["surface-100"] }]}>
        <ActivityIndicator color={c.placa} accessibilityLabel="Carregando a viagem" />
      </View>
    );
  }
  // Busca ainda rodando: as paradas não existem; a tela certa é a que acompanha a busca.
  if (dados.status === "buscando") {
    return <Redirect href={{ pathname: "/viagens/[id]/carregando", params: { id: dados.id } }} />;
  }
  return children(dados, tentarDeNovo);
}

const s = StyleSheet.create({ centro: { flex: 1, justifyContent: "center", alignItems: "center" } });
