import { router, useFocusEffect } from "expo-router";
import { useCallback, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { montarRoteiroDaViagem, type Card, type Viagem } from "@/api";
import { useCarregar } from "@/api/useCarregar";
import { espaco, estiloTexto, fontes, medida, raio, useCores } from "@/tema";
import { Aviso } from "./Aviso";
import { Button } from "./Button";
import { Ceu } from "./Ceu";
import { Destaque } from "./Destaque";
import { Estrada } from "./Estrada";
import { numero } from "./Rating";

const MINUTOS_NO_DIA = 24 * 60;
const PASSO_SAIDA = 30;
const SAIDA_PADRAO = 7 * 60;

/** "7h", "13h30": a hora do dia no formato brasileiro. */
function hora(minutos: number): string {
  const h = Math.floor(minutos / 60);
  const m = minutos % 60;
  return m ? `${h}h${String(m).padStart(2, "0")}` : `${h}h`;
}

/**
 * A hora em que a pessoa chega ao lugar: a saída mais as horas de estrada até ele.
 *
 * @param saida - Hora de saída, em minutos desde a meia-noite.
 * @param horasDeEstrada - `horas_desde_saida` do item.
 * @returns "~13h30", ou "~9h do dia 2" quando passa da meia-noite.
 */
function horaEstimada(saida: number, horasDeEstrada: number): string {
  const total = saida + Math.round(horasDeEstrada * 60);
  const dia = Math.floor(total / MINUTOS_NO_DIA);
  const texto = `~${hora(total % MINUTOS_NO_DIA)}`;
  return dia > 0 ? `${texto} do dia ${dia + 1}` : texto;
}

type Props = { viagem: Viagem };

/**
 * O roteiro da viagem (canvas Roteiro): a Estrada com origem, cidades e destino no
 * cabeçalho, os lugares de Bora na ordem do km, cada um com a hora estimada a partir da
 * hora de saída escolhida aqui, e Editar, que volta às paradas.
 */
export function RoteiroDaViagem({ viagem }: Props) {
  const { c } = useCores();
  const [saida, setSaida] = useState(SAIDA_PADRAO);
  const { dados, erro, tentarDeNovo } = useCarregar(viagem.id, montarRoteiroDaViagem);

  // Ao voltar das paradas (Editar), as decisões podem ter mudado: monta de novo.
  const primeiroFoco = useRef(true);
  useFocusEffect(
    useCallback(() => {
      if (primeiroFoco.current) primeiroFoco.current = false;
      else tentarDeNovo();
    }, [tentarDeNovo]),
  );

  if (erro) return <Aviso mensagem={erro} acao="Tentar de novo" onAcao={tentarDeNovo} />;

  const itens = dados?.itens ?? [];
  const destino = viagem.paradas.find((p) => p.tipo === "destino");
  const totalKm = destino?.km_na_rota ?? null;
  const cidades = [viagem.origem, ...viagem.paradas.map((p) => p.nome)].map((cidade) => cidade.split(",")[0]);
  const resumo = [
    totalKm != null ? `KM ${numero(totalKm)}` : null,
    `${numero(itens.length)} ${itens.length === 1 ? "lugar" : "lugares"}`,
  ]
    .filter(Boolean)
    .join(" · ");
  const editar = () => router.push({ pathname: "/viagens/[id]/paradas", params: { id: viagem.id } });
  const mudarSaida = (delta: number) => setSaida((s) => (s + delta + MINUTOS_NO_DIA) % MINUTOS_NO_DIA);

  return (
    <View style={s.tela}>
      <Ceu serra>
        <Text style={[estiloTexto("km"), s.maiusculas, { color: c["ink-muted"] }]}>
          {viagem.origem} → {viagem.destino}
        </Text>
        <Text style={[estiloTexto("km"), s.maiusculas, { color: c["ink-muted"] }]}>{resumo}</Text>
        <Text accessibilityRole="header" style={[estiloTexto("display-l"), { color: c.ink }]}>
          Seu roteiro está <Destaque>pronto</Destaque>
        </Text>
        <View style={s.faixaEstrada}>
          <View style={s.recorteEstrada}>
            <Estrada cidades={cidades} variante="curva" largura={medida.roteiroEstradaLargura} />
          </View>
        </View>
      </Ceu>

      <View style={s.saida}>
        <Text style={[estiloTexto("body-strong"), { color: c.ink }]}>Saída</Text>
        <View style={s.seletor}>
          <BotaoHora rotulo="−" leitura="30 minutos mais cedo" onPress={() => mudarSaida(-PASSO_SAIDA)} />
          <Text
            accessibilityLabel={`Saída às ${hora(saida)}`}
            accessibilityLiveRegion="polite"
            style={[estiloTexto("km"), s.horaSaida, { color: c.ink }]}
          >
            {hora(saida)}
          </Text>
          <BotaoHora rotulo="+" leitura="30 minutos mais tarde" onPress={() => mudarSaida(PASSO_SAIDA)} />
        </View>
      </View>

      {!dados ? (
        <View style={s.centro}>
          <ActivityIndicator color={c.placa} accessibilityLabel="Montando o roteiro" />
        </View>
      ) : itens.length === 0 ? (
        <View style={s.centro}>
          <Text style={[estiloTexto("body"), s.vazio, { color: c["ink-muted"] }]}>
            Nenhum lugar com Bora ainda. Volte às paradas e escolha os seus.
          </Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={s.lista}>
          {itens.map((item, i) => (
            <ItemRoteiro key={item.id} item={item} posicao={i + 1} saida={saida} />
          ))}
        </ScrollView>
      )}

      <View style={s.rodape}>
        <Button block variant="secondary" onPress={editar}>
          Editar
        </Button>
      </View>
    </View>
  );
}

function BotaoHora({ rotulo, leitura, onPress }: { rotulo: string; leitura: string; onPress: () => void }) {
  const { c } = useCores();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={leitura}
      style={({ pressed }) => [
        s.botaoHora,
        { backgroundColor: pressed ? c["surface-300"] : c["surface-200"] },
      ]}
    >
      <Text style={[estiloTexto("title"), { color: c.ink }]}>{rotulo}</Text>
    </Pressable>
  );
}

function ItemRoteiro({ item, posicao, saida }: { item: Card; posicao: number; saida: number }) {
  const { c } = useCores();
  const quando = [item.cidade, item.horas_desde_saida != null ? horaEstimada(saida, item.horas_desde_saida) : null]
    .filter(Boolean)
    .join(" · ");
  const km = item.km_na_rota != null ? `KM ${numero(item.km_na_rota)}` : "";
  return (
    <View
      accessible
      accessibilityLabel={[`${posicao}`, item.nome, quando, km].filter(Boolean).join(", ")}
      style={[s.item, { backgroundColor: c["surface-200"] }]}
    >
      <View style={[s.numero, { backgroundColor: c.asfalto }]}>
        <Text style={[estiloTexto("km"), { color: c["on-asfalto"], fontFamily: fontes.placaForte }]}>{posicao}</Text>
      </View>
      <View style={s.info}>
        <Text style={[estiloTexto("body-strong"), { color: c.ink }]}>{item.nome ?? "Lugar"}</Text>
        {quando ? <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>{quando}</Text> : null}
      </View>
      <Text style={[estiloTexto("km"), { color: c["ink-muted"] }]}>{km}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  maiusculas: { textTransform: "uppercase" },
  faixaEstrada: {
    height: medida.roteiroEstradaAltura,
    marginHorizontal: -espaco["space-4"],
    marginBottom: -espaco["space-4"],
    overflow: "hidden",
  },
  recorteEstrada: { marginTop: -medida.roteiroEstradaRecorte },
  saida: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: espaco["space-4"],
    paddingVertical: espaco["space-2"],
  },
  seletor: { flexDirection: "row", alignItems: "center", gap: espaco["space-3"] },
  horaSaida: { minWidth: espaco.touch, textAlign: "center" },
  botaoHora: {
    width: espaco.touch,
    height: espaco.touch,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: raio["radius-pill"],
  },
  centro: { flex: 1, justifyContent: "center", alignItems: "center", padding: espaco["space-6"] },
  vazio: { textAlign: "center" },
  lista: { gap: espaco["space-2"], paddingHorizontal: espaco["space-4"], paddingBottom: espaco["space-4"] },
  item: {
    flexDirection: "row",
    alignItems: "center",
    gap: espaco["space-3"],
    padding: espaco["space-3"],
    borderRadius: raio["radius-md"],
  },
  numero: {
    width: medida.roteiroNumero,
    height: medida.roteiroNumero,
    borderRadius: raio["radius-pill"],
    alignItems: "center",
    justifyContent: "center",
  },
  info: { flex: 1, minWidth: 0 },
  rodape: { paddingHorizontal: espaco["space-4"], paddingVertical: espaco["space-4"] },
});
