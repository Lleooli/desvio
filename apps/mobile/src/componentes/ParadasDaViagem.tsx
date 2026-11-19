import { router, useFocusEffect } from "expo-router";
import { useCallback, useRef } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { ParadaDaViagem, Viagem } from "@/api";
import { espaco, estiloTexto, raio, useCores } from "@/tema";
import { Button } from "./Button";
import { Destaque } from "./Destaque";
import { numero } from "./Rating";
import { StopItem } from "./StopItem";

/** As paradas na ordem da estrada: por km, com o destino sempre no fim. */
function naOrdemDaEstrada(paradas: ParadaDaViagem[]): ParadaDaViagem[] {
  const km = (p: ParadaDaViagem) => p.km_na_rota ?? Infinity;
  const fim = (p: ParadaDaViagem) => (p.tipo === "destino" ? 1 : 0);
  return [...paradas].sort((a, b) => fim(a) - fim(b) || km(a) - km(b) || a.ordem - b.ordem);
}

type Props = {
  viagem: Viagem;
  /** Busca a viagem de novo; chamado ao voltar para a tela (do swipe, por exemplo). */
  recarregar: () => void;
};

/**
 * A linha do tempo da viagem (canvas Paradas): origem no topo, as paradas por km e o
 * destino no fim, cada uma com quantos lugares tiveram Bora. A parada atual é a primeira
 * com cards sem decisão; o toque abre o swipe da parada.
 */
export function ParadasDaViagem({ viagem, recarregar }: Props) {
  const { c } = useCores();
  const paradas = naOrdemDaEstrada(viagem.paradas);
  const atual = paradas.find((p) => p.cards.length > 0);
  const aceitos = paradas.reduce((soma, p) => soma + p.progresso.aceitos, 0);

  // O contador muda no swipe: ao voltar para a tela, busca de novo. A primeira vez já veio carregada.
  const primeiroFoco = useRef(true);
  useFocusEffect(
    useCallback(() => {
      if (primeiroFoco.current) primeiroFoco.current = false;
      else recarregar();
    }, [recarregar]),
  );

  const abrirSwipe = (p: ParadaDaViagem) =>
    router.push({ pathname: "/viagens/[id]/paradas/[paradaId]", params: { id: viagem.id, paradaId: String(p.ordem) } });
  const montarRoteiro = () => router.push({ pathname: "/viagens/[id]/roteiro", params: { id: viagem.id } });

  return (
    <View style={s.tela}>
      <ScrollView contentContainerStyle={s.conteudo}>
        <View style={s.cabecalho}>
          <Text style={[estiloTexto("km"), s.trajeto, { color: c["ink-muted"] }]}>
            {viagem.origem} → {viagem.destino}
          </Text>
          <Text accessibilityRole="header" style={[estiloTexto("display-xl"), { color: c.ink }]}>
            Escolha suas <Destaque>paradas</Destaque>
          </Text>
          <Text style={[estiloTexto("body"), { color: c["ink-muted"] }]}>Toque numa cidade para deslizar os lugares dela.</Text>
        </View>
        <View style={[s.linhaDoTempo, { backgroundColor: c["surface-200"] }]}>
          <StopItem tipo="origem" cidade={viagem.origem} km={0} horas={0} />
          {paradas.map((p) => (
            <Pressable
              key={p.ordem}
              onPress={() => abrirSwipe(p)}
              accessibilityRole="button"
              accessibilityHint="Abre os lugares desta parada"
              style={({ pressed }) => pressed && { backgroundColor: c["surface-300"] }}
            >
              <StopItem
                cidade={p.nome}
                uf={p.uf ?? undefined}
                km={p.km_na_rota ?? undefined}
                horas={p.horas_desde_saida ?? undefined}
                tipo={p.tipo === "destino" ? "destino" : "parada"}
                ativo={p === atual}
                aceitos={p.progresso.aceitos}
                total={p.progresso.total}
              />
            </Pressable>
          ))}
        </View>
      </ScrollView>
      <View style={s.rodape}>
        <Button block icon="route" disabled={aceitos === 0} onPress={montarRoteiro}>
          {aceitos === 0
            ? "Montar roteiro"
            : `Montar roteiro com ${numero(aceitos)} ${aceitos === 1 ? "lugar" : "lugares"}`}
        </Button>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  conteudo: { paddingBottom: espaco["space-4"] },
  cabecalho: {
    gap: espaco["space-2"],
    paddingTop: espaco["space-6"],
    paddingHorizontal: espaco["space-4"],
    paddingBottom: espaco["space-2"],
  },
  trajeto: { textTransform: "uppercase" },
  linhaDoTempo: {
    marginTop: espaco["space-2"],
    marginHorizontal: espaco["space-4"],
    paddingTop: espaco["space-4"],
    paddingRight: espaco["space-3"],
    paddingBottom: espaco["space-1"],
    borderRadius: raio["radius-md"],
  },
  rodape: { paddingHorizontal: espaco["space-4"], paddingVertical: espaco["space-4"] },
});
