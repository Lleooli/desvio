import { Redirect, router, useFocusEffect, useNavigation } from "expo-router";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ActivityIndicator, AppState, StyleSheet, View } from "react-native";
import { obterViagem, type Viagem } from "@/api";
import { useCarregar } from "@/api/useCarregar";
import { useCores } from "@/tema";
import { esquecerViagemAtiva, useViagemAtiva } from "@/viagemAtiva";
import { Aviso } from "./Aviso";

const INTERVALO_ATUALIZAR_MS = 10_000;

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
  const { dados, erro, tipoErro, carregando, tentarDeNovo, atualizar } = useCarregar(viagemId, obterViagem);
  useAtualizarEnquantoBusca(dados?.id === viagemId && dados.status === "buscando", atualizar);

  if (!id && ativa.carregou && !ativa.id) {
    return <Aviso mensagem="Você ainda não abriu nenhuma viagem." acao="Ver viagens" onAcao={() => router.navigate("/viagens")} />;
  }
  if (erro && (tipoErro === "nao-encontrado" || tipoErro === "sessao")) {
    const destino = tipoErro === "sessao" ? "/entrar" : "/viagens";
    const sair = () => {
      // Sessão vencida não é motivo para perder a viagem: depois do login ela volta.
      if (tipoErro === "nao-encontrado") esquecerViagemAtiva();
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
  // Busca rodando ou que falhou, sem cards ainda: a tela certa é a Carregando, que acompanha
  // a busca ou mostra a falha com Tentar de novo. Com os cards do parcial (só OpenStreetMap),
  // a busca segue, mas as paradas e o swipe já abrem; a viagem é buscada de novo a cada 10 s.
  if ((dados.status === "buscando" && !temCards(dados)) || dados.status === "falhou") {
    if (!id) return <AcompanharBusca viagemId={dados.id} falhou={dados.status === "falhou"} recarregar={tentarDeNovo} />;
    return <Redirect href={{ pathname: "/viagens/[id]/carregando", params: { id: dados.id } }} />;
  }
  return children(dados, tentarDeNovo);
}

/** A viagem já tem cards nas paradas, mesmo os já decididos (o parcial chegou). */
export function temCards(viagem: Viagem): boolean {
  return viagem.paradas.some((p) => p.progresso.total > 0);
}

/**
 * Enquanto `buscando`, chama `atualizar` a cada 10 s, só com a tela em foco e o app em
 * primeiro plano. Os cards que o Google trouxer entram nas paradas e no swipe sem a
 * pessoa sair da tela.
 */
function useAtualizarEnquantoBusca(buscando: boolean, atualizar: () => void) {
  const [focada, setFocada] = useState(false);
  const [ativo, setAtivo] = useState(AppState.currentState === "active");
  useFocusEffect(
    useCallback(() => {
      setFocada(true);
      return () => setFocada(false);
    }, []),
  );
  useEffect(() => {
    const assinatura = AppState.addEventListener("change", (estado) => setAtivo(estado === "active"));
    return () => assinatura.remove();
  }, []);
  useEffect(() => {
    if (!buscando || !focada || !ativo) return;
    const relogio = setInterval(atualizar, INTERVALO_ATUALIZAR_MS);
    return () => clearInterval(relogio);
  }, [buscando, focada, ativo, atualizar]);
}

/**
 * Numa aba, abre a tela Carregando por cima das abas (push), e não no lugar delas: o
 * `<Redirect>` trocaria a rota `(abas)` inteira, e o voltar do Android fecharia o app.
 * Ao voltar para a aba, busca a viagem de novo, para mostrar as paradas se a busca acabou.
 * O push automático só acontece no primeiro foco: a aba escondida embaixo da pilha também
 * ouve a viagem ativa, e empilharia uma segunda Carregando da mesma viagem.
 */
function AcompanharBusca({ viagemId, falhou, recarregar }: { viagemId: string; falhou: boolean; recarregar: () => void }) {
  const acompanhar = useCallback(() => router.push({ pathname: "/viagens/[id]/carregando", params: { id: viagemId } }), [viagemId]);
  // Montada numa aba escondida (fora de foco), não empurra a Carregando no primeiro foco:
  // os dados podem estar velhos. Nesse caso o foco só busca a viagem de novo.
  const navegacao = useNavigation();
  const abriu = useRef(!navegacao.isFocused());
  useFocusEffect(
    useCallback(() => {
      if (abriu.current) {
        recarregar();
      } else {
        abriu.current = true;
        acompanhar();
      }
    }, [acompanhar, recarregar]),
  );
  return falhou ? (
    <Aviso mensagem="A busca das paradas falhou." acao="Ver a busca" onAcao={acompanhar} />
  ) : (
    <Aviso mensagem="A busca das paradas ainda está rodando." acao="Acompanhar" onAcao={acompanhar} />
  );
}

const s = StyleSheet.create({ centro: { flex: 1, justifyContent: "center", alignItems: "center" } });
