import { router } from "expo-router";
import type { ReactNode } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { obterViagem, type Viagem } from "@/api";
import { useCarregar } from "@/api/useCarregar";
import { useCores } from "@/tema";
import { esquecerViagemAtiva, useViagemAtiva } from "@/viagemAtiva";
import { Aviso } from "./Aviso";

/**
 * Para as abas Descobrir e Roteiro: carrega a viagem ativa e só desenha `children` com ela.
 * Sem viagem aberta, leva para Minhas viagens; com erro, mostra a mensagem e Tentar de novo.
 * Viagem que não existe mais (ou é de outra conta) e sessão vencida não se resolvem tentando
 * de novo: esquece a viagem ativa e leva para Minhas viagens ou para o login.
 */
export function NaViagemAtiva({ children }: { children: (viagem: Viagem) => ReactNode }) {
  const { c } = useCores();
  const ativa = useViagemAtiva();
  const { dados, erro, tipoErro, carregando, tentarDeNovo } = useCarregar(ativa.id, obterViagem);

  if (ativa.carregou && !ativa.id) {
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
  if (carregando || !dados) {
    return (
      <View style={[s.centro, { backgroundColor: c["surface-100"] }]}>
        <ActivityIndicator color={c.placa} accessibilityLabel="Carregando a viagem" />
      </View>
    );
  }
  return children(dados);
}

const s = StyleSheet.create({ centro: { flex: 1, justifyContent: "center", alignItems: "center" } });
