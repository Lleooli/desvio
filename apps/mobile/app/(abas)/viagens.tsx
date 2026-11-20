import { router, useFocusEffect } from "expo-router";
import { useCallback, useRef } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { listarViagens, obterJob, type ResumoViagem, type Veiculo } from "@/api";
import { useCarregar } from "@/api/useCarregar";
import { Aviso } from "@/componentes/Aviso";
import { Button } from "@/componentes/Button";
import { Destaque } from "@/componentes/Destaque";
import { Icon, type IconName } from "@/componentes/Icon";
import { numero } from "@/componentes/Rating";
import { espaco, estiloTexto, raio, tamanhoIcone, useCores } from "@/tema";
import { definirViagemAtiva } from "@/viagemAtiva";

const veiculos: Record<Veiculo, { icone: IconName; nome: string }> = {
  carro: { icone: "car", nome: "Carro" },
  moto: { icone: "moto", nome: "Moto" },
  bicicleta: { icone: "bike", nome: "Bicicleta" },
};

const nomeStatus = { buscando: "Buscando", pronta: "Pronta", falhou: "Busca falhou" } as const;

/** Minhas viagens (HU04, HU06): a lista das viagens e o ponto de partida para criar uma nova. */
export default function Viagens() {
  const { c } = useCores();
  const margens = useSafeAreaInsets();
  const { dados, erro, tipoErro, tentarDeNovo } = useCarregar("eu", listarViagens);

  // Status e progresso mudam fora desta tela (worker, swipe): ao voltar para ela, busca de novo.
  const primeiroFoco = useRef(true);
  useFocusEffect(
    useCallback(() => {
      if (primeiroFoco.current) primeiroFoco.current = false;
      else tentarDeNovo();
    }, [tentarDeNovo]),
  );

  if (erro && tipoErro === "sessao") return <Aviso mensagem={erro} acao="Entrar" onAcao={() => router.navigate("/entrar")} />;
  if (erro && !dados) return <Aviso mensagem={erro} acao="Tentar de novo" onAcao={tentarDeNovo} />;

  return (
    <ScrollView
      style={{ backgroundColor: c["surface-100"] }}
      contentContainerStyle={[s.conteudo, { paddingTop: margens.top + espaco["space-6"] }]}
    >
      <View style={s.cabecalho}>
        <Text accessibilityRole="header" style={[estiloTexto("display-xl"), { color: c.ink }]}>
          Suas <Destaque>viagens</Destaque>
        </Text>
        <Button block icon="route" onPress={() => router.push("/viagens/nova")}>
          Nova viagem
        </Button>
      </View>
      {!dados ? (
        <ActivityIndicator color={c.placa} accessibilityLabel="Carregando suas viagens" style={s.carregando} />
      ) : dados.length === 0 ? (
        <View style={s.vazio}>
          <Text style={[estiloTexto("title"), { color: c.ink }]}>Sua primeira viagem começa aqui</Text>
          <Text style={[estiloTexto("body"), { color: c["ink-muted"] }]}>
            Diga de onde você sai e para onde vai. O Desvio acha os lugares no caminho para você escolher.
          </Text>
        </View>
      ) : (
        <View style={s.lista}>
          <Text style={[estiloTexto("label"), s.secao, { color: c["ink-muted"] }]}>Em planejamento</Text>
          {dados.map((v) => (
            <CartaoViagem key={v.id} viagem={v} />
          ))}
        </View>
      )}
    </ScrollView>
  );
}

/** Uma viagem da lista: o toque marca a viagem como ativa e abre o Carregando (em busca) ou as paradas. */
function CartaoViagem({ viagem }: { viagem: ResumoViagem }) {
  const { c, sombra } = useCores();
  const pronta = viagem.status === "pronta";
  const veiculo = veiculos[viagem.veiculo];

  const abrir = () => {
    definirViagemAtiva(viagem.id);
    const pathname = pronta ? "/viagens/[id]/paradas" : "/viagens/[id]/carregando";
    router.push({ pathname, params: { id: viagem.id } });
  };

  return (
    <Pressable
      onPress={abrir}
      accessibilityRole="button"
      accessibilityHint={pronta ? "Abre as paradas desta viagem" : "Abre o andamento da busca"}
      style={({ pressed }) => [
        s.cartao,
        { backgroundColor: pressed ? c["surface-300"] : c["surface-200"], boxShadow: sombra["shadow-1"] },
      ]}
    >
      <View style={[s.icone, { backgroundColor: pronta ? c.placa : c["surface-300"] }]}>
        <Icon name={veiculo.icone} size={tamanhoIcone.nav} color={pronta ? c["on-placa"] : c.ink} />
      </View>
      <View style={s.textos}>
        <Text style={[estiloTexto("title"), { color: c.ink }]}>
          {viagem.origem} → {viagem.destino}
        </Text>
        <Text style={[estiloTexto("km"), s.placa, { color: c["ink-muted"] }]}>
          {veiculo.nome} · {nomeStatus[viagem.status]}
        </Text>
        {viagem.status === "buscando" ? (
          <ProgressoDaBusca jobId={viagem.job_id} />
        ) : viagem.status === "falhou" ? (
          <Text style={[estiloTexto("body-s"), { color: c.perigo }]}>A busca não deu certo · ver o que houve</Text>
        ) : (
          <ProgressoDasDecisoes {...viagem.progresso} />
        )}
      </View>
    </Pressable>
  );
}

/** Quantos lugares da viagem já tiveram decisão: "3 de 12 lugares decididos · continuar". */
function ProgressoDasDecisoes({ decididos, total }: ResumoViagem["progresso"]) {
  const { c } = useCores();
  if (decididos === 0) {
    return <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>Nenhum lugar decidido ainda</Text>;
  }
  return (
    <Text style={[estiloTexto("body-strong"), s.progresso, { color: c.placa }]}>
      {numero(decididos)} de {numero(total)} {total === 1 ? "lugar decidido" : "lugares decididos"} · continuar
    </Text>
  );
}

/** A etapa e o percentual da busca em andamento, pelo job da viagem. */
function ProgressoDaBusca({ jobId }: { jobId: string | null }) {
  const { c } = useCores();
  const { dados } = useCarregar(jobId, obterJob);
  const etapa = dados?.progresso;
  return (
    <Text style={[estiloTexto("body-strong"), s.progresso, { color: c.placa }]}>
      {etapa ? `${etapa.titulo} · ${numero(etapa.percentual)}%` : "Procurando paradas no caminho"}
    </Text>
  );
}

const s = StyleSheet.create({
  conteudo: { paddingHorizontal: espaco["space-4"], paddingBottom: espaco["space-6"], gap: espaco["space-6"] },
  cabecalho: { gap: espaco["space-6"] },
  carregando: { marginTop: espaco["space-8"] },
  vazio: { gap: espaco["space-2"] },
  lista: { gap: espaco["space-3"] },
  secao: { textTransform: "uppercase" },
  cartao: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: espaco["space-3"],
    padding: espaco["space-4"],
    borderRadius: raio["radius-md"],
  },
  icone: {
    width: espaco["space-8"] + espaco["space-3"],
    height: espaco["space-8"] + espaco["space-3"],
    borderRadius: raio["radius-pill"],
    alignItems: "center",
    justifyContent: "center",
  },
  textos: { flex: 1, minWidth: 0, gap: espaco["space-1"] },
  placa: { textTransform: "uppercase" },
  progresso: { fontSize: estiloTexto("body-s").fontSize, lineHeight: estiloTexto("body-s").lineHeight },
});
