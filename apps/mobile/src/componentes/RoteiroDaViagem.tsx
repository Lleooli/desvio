import { router, useFocusEffect } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Linking, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, { runOnJS, useAnimatedStyle, useSharedValue } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  editarRoteiroDaViagem,
  mensagemDeErro,
  montarRoteiroDaViagem,
  type Card,
  type Noite,
  type Roteiro,
  type Viagem,
} from "@/api";
import { useCarregar } from "@/api/useCarregar";
import { LIMITE_PARADAS_GOOGLE, linkWaze, trechosGoogleMaps } from "@/mapas";
import { espaco, estiloTexto, fontes, medida, raio, tamanhoIcone, useCores } from "@/tema";
import { Aviso } from "./Aviso";
import { Button } from "./Button";
import { Ceu } from "./Ceu";
import { Destaque } from "./Destaque";
import { Estrada } from "./Estrada";
import { Icon } from "./Icon";
import { numero } from "./Rating";
import { Toast } from "./Toast";

const MINUTOS_NO_DIA = 24 * 60;
const PASSO_SAIDA = 30;
const SAIDA_PADRAO = 7 * 60;
/** Espera a pessoa parar de mexer na saída antes de pedir à IA um roteiro novo. */
const ESPERA_SAIDA_MS = 800;
/** Quanto tempo o Desfazer fica na tela depois de tirar um lugar. */
const DURACAO_DESFAZER_MS = 4000;
/** Segurar o item antes de arrastar, para não brigar com a rolagem da lista. */
const SEGURAR_PARA_ARRASTAR_MS = 300;

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

/** "07:30" em minutos desde a meia-noite; undefined fora do formato. */
function minutosDe(hhmm: string | null | undefined): number | undefined {
  const partes = hhmm ? /^([01]\d|2[0-3]):([0-5]\d)$/.exec(hhmm) : null;
  return partes ? Number(partes[1]) * 60 + Number(partes[2]) : undefined;
}

/**
 * As noites do coletor conferidas com os itens que estão na tela: tirar o hotel do
 * roteiro (ou desfazer) muda a noite na hora, sem esperar o coletor.
 */
function noitesNaTela(noites: Noite[], itens: Card[]): Noite[] {
  return noites.map((noite) => {
    const hoteis = itens.filter((item) => item.categoria === "hospedagem" && item.cidade === noite.cidade);
    const hotel = hoteis.find((item) => item.pernoite) ?? hoteis[0];
    return hotel
      ? { ...noite, hotel: { id: hotel.id, nome: hotel.nome ?? null }, aviso: null }
      : { ...noite, hotel: null, aviso: `Falta escolher onde dormir em ${noite.cidade}` };
  });
}

/** A lista com o item de `de` levado `passos` posições para baixo (negativo: para cima). */
function mover<T>(lista: T[], de: number, passos: number): T[] {
  const para = Math.max(0, Math.min(lista.length - 1, de + passos));
  if (para === de) return lista;
  const nova = [...lista];
  const [item] = nova.splice(de, 1);
  nova.splice(para, 0, item);
  return nova;
}

/** "07:00": a hora de saída no formato que o coletor recebe. */
function horaHHMM(minutos: number): string {
  return `${String(Math.floor(minutos / 60)).padStart(2, "0")}:${String(minutos % 60).padStart(2, "0")}`;
}

/**
 * Quantos dias a viagem ocupa, saindo à hora escolhida: o mesmo relógio de `horaEstimada`.
 *
 * @param saida - Hora de saída, em minutos desde a meia-noite.
 * @param horasDeEstrada - `horas_desde_saida` do destino.
 * @returns 1 quando chega no mesmo dia; undefined sem as horas do destino.
 */
function diasDeViagem(saida: number, horasDeEstrada: number | null | undefined): number | undefined {
  if (horasDeEstrada == null) return undefined;
  return Math.floor((saida + Math.round(horasDeEstrada * 60)) / MINUTOS_NO_DIA) + 1;
}

type Props = {
  viagem: Viagem;
  /** Busca a viagem de novo (GET, sem IA), para saber se as decisões mudaram. */
  recarregar: () => void;
};

/**
 * O roteiro da viagem (canvas Roteiro): a Estrada com origem, cidades e destino no
 * cabeçalho, os lugares de Bora na ordem que a IA ajustou à hora de saída escolhida aqui
 * (ou na do km, quando a IA não responde), cada um com a hora estimada e o porquê,
 * Editar, que volta às paradas, e Abrir no mapa (HU13, HU14). A pessoa reordena (botões
 * ou segurar e arrastar) e tira lugares; a ordem dela fica guardada e o Bora continua (HU15).
 */
export function RoteiroDaViagem({ viagem, recarregar }: Props) {
  const { c } = useCores();
  // Começa na hora de saída da Nova viagem; viagens de antes dela começam às 7h.
  const saidaDaViagem = minutosDe(viagem.saida) ?? SAIDA_PADRAO;
  const [saida, setSaida] = useState(saidaDaViagem);
  const [saidaPedida, setSaidaPedida] = useState(saidaDaViagem);
  const [mapaAberto, setMapaAberto] = useState(false);
  const destino = viagem.paradas.find((p) => p.tipo === "destino");

  // Cada toque no seletor mudaria a saída; a IA só é chamada quando a pessoa para.
  useEffect(() => {
    const relogio = setTimeout(() => setSaidaPedida(saida), ESPERA_SAIDA_MS);
    return () => clearTimeout(relogio);
  }, [saida]);

  // Cada montagem chama o Groq (cota pequena, da conta toda): só monta de novo quando a
  // saída ou as decisões mudam, e não a cada vez que a aba ganha foco.
  const decisoes = `${viagem.progresso.decididos}/${viagem.progresso.total}`;
  const { dados, erro, tentarDeNovo } = useCarregar(`${viagem.id}@${saidaPedida}@${decisoes}`, () =>
    montarRoteiroDaViagem(viagem.id, {
      usar_ia: true,
      contexto: {
        saida: horaHHMM(saidaPedida),
        dias: diasDeViagem(saidaPedida, destino?.horas_desde_saida),
        ...(viagem.data ? { data: viagem.data } : {}),
      },
    }),
  );

  // A edição aparece na hora; o coletor guarda em segundo plano.
  const [editado, setEditado] = useState<Roteiro | null>(null);
  const [erroEdicao, setErroEdicao] = useState<string | null>(null);
  const [tirado, setTirado] = useState<{ nome: string; antes: Roteiro } | null>(null);
  const filaDeEdicoes = useRef<Promise<void>>(Promise.resolve());
  const ultimoPedido = useRef(0);
  useEffect(() => setEditado(null), [dados]);
  useEffect(() => {
    if (!tirado) return;
    const relogio = setTimeout(() => setTirado(null), DURACAO_DESFAZER_MS);
    return () => clearTimeout(relogio);
  }, [tirado]);

  // Ao voltar das paradas (Editar), as decisões podem ter mudado: busca a viagem de novo
  // (sem IA). Se o progresso mudou, a chave acima muda e o roteiro é montado outra vez.
  const primeiroFoco = useRef(true);
  useFocusEffect(
    useCallback(() => {
      if (primeiroFoco.current) primeiroFoco.current = false;
      else recarregar();
    }, [recarregar]),
  );

  if (erro) return <Aviso mensagem={erro} acao="Tentar de novo" onAcao={tentarDeNovo} />;

  const roteiro = editado ?? dados;
  const itens = roteiro?.itens ?? [];
  const noites = noitesNaTela(dados?.noites ?? [], itens);
  const totalKm = destino?.km_na_rota ?? null;
  const cidades = [viagem.origem, ...viagem.paradas.map((p) => p.nome)].map((cidade) => cidade.split(",")[0]);
  // Enquanto a IA monta, ainda não há lugares para contar: "0 lugares" e "pronto" seriam falsos.
  const montando = !roteiro;
  const resumo = [
    totalKm != null ? `KM ${numero(totalKm)}` : null,
    montando ? null : `${numero(itens.length)} ${itens.length === 1 ? "lugar" : "lugares"}`,
  ]
    .filter(Boolean)
    .join(" · ");
  const editar = () => router.push({ pathname: "/viagens/[id]/paradas", params: { id: viagem.id } });
  const mudarSaida = (delta: number) => setSaida((s) => (s + delta + MINUTOS_NO_DIA) % MINUTOS_NO_DIA);

  /**
   * Mostra a ordem nova na hora e guarda; se o coletor recusar, volta à de antes.
   * Os PUTs saem um de cada vez, na ordem dos toques, e a falha de um que já foi
   * superado por outro é ignorada: a tela mostra o que o último guardou.
   */
  const guardar = (novos: Card[]) => {
    if (!roteiro) return;
    const antes = roteiro;
    const pedido = ++ultimoPedido.current;
    setEditado({ itens: novos, explicacoes: {}, fonte: "pessoa" });
    setErroEdicao(null);
    filaDeEdicoes.current = filaDeEdicoes.current
      .then(() =>
        editarRoteiroDaViagem(
          viagem.id,
          novos.map((item) => item.id),
        ),
      )
      .then(
        () => undefined,
        (e: unknown) => {
          if (pedido !== ultimoPedido.current) return;
          setEditado(antes);
          setErroEdicao(mensagemDeErro(e));
        },
      );
  };
  const moverItem = (de: number, passos: number) => {
    const novos = mover(itens, de, passos);
    if (novos !== itens) guardar(novos);
  };
  const tirarItem = (de: number) => {
    if (!roteiro) return;
    setTirado({ nome: itens[de].nome ?? "Lugar", antes: roteiro });
    guardar(itens.filter((_, i) => i !== de));
  };
  const desfazer = () => {
    if (!tirado) return;
    guardar(tirado.antes.itens);
    setTirado(null);
  };

  return (
    <View style={s.tela}>
      {/* Uma rolagem só: o cabeçalho e a Saída sobem junto com a lista. */}
      <ScrollView contentContainerStyle={s.rolagem}>
        <Ceu serra>
          <Text style={[estiloTexto("km"), s.maiusculas, { color: c["ink-muted"] }]}>
            {viagem.origem} → {viagem.destino}
          </Text>
          <Text style={[estiloTexto("km"), s.maiusculas, { color: c["ink-muted"] }]}>{resumo}</Text>
          <Text accessibilityRole="header" style={[estiloTexto("display-l"), { color: c.ink }]}>
            {montando ? (
              <>
                Montando seu <Destaque>roteiro</Destaque>
              </>
            ) : (
              <>
                Seu roteiro está <Destaque>pronto</Destaque>
              </>
            )}
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

        {!roteiro ? (
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
          <View style={s.lista}>
            {roteiro.fonte === "geometria" ? (
              <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>
                Por agora, a ordem segue o km da estrada.
              </Text>
            ) : null}
            {erroEdicao ? (
              <Text accessibilityLiveRegion="polite" style={[estiloTexto("body-s"), { color: c.ink }]}>
                {erroEdicao}
              </Text>
            ) : null}
            {noites.length > 0 ? <NoitesDaViagem viagemId={viagem.id} noites={noites} /> : null}
            {itens.map((item, i) => (
              <ItemRoteiro
                key={item.id}
                item={item}
                posicao={i + 1}
                total={itens.length}
                saida={saida}
                porque={roteiro.explicacoes[item.id]}
                onMover={(passos) => moverItem(i, passos)}
                onTirar={() => tirarItem(i)}
              />
            ))}
          </View>
        )}
      </ScrollView>

      {tirado ? (
        <Toast icon="x" acao="Desfazer" onAcao={desfazer}>
          {`${tirado.nome} saiu do roteiro`}
        </Toast>
      ) : null}

      <View style={s.rodape}>
        <View style={s.editar}>
          <Button block variant="secondary" onPress={editar}>
            Editar
          </Button>
        </View>
        <View style={s.abrirNoMapa}>
          <Button block icon="route" disabled={itens.length === 0} onPress={() => setMapaAberto(true)}>
            Abrir no mapa
          </Button>
        </View>
      </View>

      {/* A key muda quando o roteiro muda (Editar): a próxima do Waze volta ao primeiro lugar. */}
      <AbrirNoMapa
        key={itens.map((item) => item.id).join(",")}
        viagem={viagem}
        itens={itens}
        visivel={mapaAberto}
        onFechar={() => setMapaAberto(false)}
      />
    </View>
  );
}

/**
 * Onde a pessoa dorme em cada noite (issue #104): o hotel aceito na cidade de estadia, ou
 * o aviso de que falta escolher, com o atalho para o swipe dessa parada.
 */
function NoitesDaViagem({ viagemId, noites }: { viagemId: string; noites: Noite[] }) {
  const { c } = useCores();
  const escolher = (parada: number) =>
    router.push({ pathname: "/viagens/[id]/paradas/[paradaId]", params: { id: viagemId, paradaId: String(parada) } });
  return (
    <View style={[s.noites, { backgroundColor: c["surface-200"] }]}>
      <Text accessibilityRole="header" style={[estiloTexto("body-strong"), { color: c.ink }]}>
        Onde você dorme
      </Text>
      {noites.map((noite) => (
        <View key={noite.dia} style={s.noite}>
          <Icon name="bed" size={tamanhoIcone.padrao} color={noite.hotel ? c.placa : c.perigo} />
          <View style={s.info}>
            <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>{`Dia ${noite.dia} · ${noite.cidade}`}</Text>
            <Text
              accessibilityLiveRegion="polite"
              style={[estiloTexto(noite.hotel ? "body-strong" : "body"), { color: c.ink }]}
            >
              {noite.hotel ? (noite.hotel.nome ?? "Hotel escolhido") : noite.aviso}
            </Text>
          </View>
          {!noite.hotel && noite.parada != null ? (
            <Button size="sm" variant="secondary" onPress={() => escolher(noite.parada as number)}>
              Escolher
            </Button>
          ) : null}
        </View>
      ))}
    </View>
  );
}

type PropsMapa = { viagem: Viagem; itens: Card[]; visivel: boolean; onFechar: () => void };

/**
 * Painel de Abrir no mapa: o Google Maps com os lugares como pontos de passagem, em
 * trechos numerados quando passam do limite do app, e o Waze, que só aceita um destino
 * e por isso abre a próxima parada; cada vez que abre, a próxima avança.
 */
function AbrirNoMapa({ viagem, itens, visivel, onFechar }: PropsMapa) {
  const { c } = useCores();
  const margens = useSafeAreaInsets();
  const [proxima, setProxima] = useState(0);
  if (itens.length === 0) return null;

  const trechos = trechosGoogleMaps(viagem.origem, viagem.destino, itens, viagem.veiculo);
  const indiceWaze = Math.min(proxima, itens.length - 1);
  const lugarWaze = itens[indiceWaze];
  const abrirWaze = () => {
    Linking.openURL(linkWaze(lugarWaze));
    setProxima(indiceWaze + 1);
  };

  return (
    <Modal visible={visivel} transparent animationType="slide" onRequestClose={onFechar}>
      <Pressable accessibilityLabel="Fechar" style={[s.veu, { backgroundColor: c.scrim }]} onPress={onFechar} />
      <View
        style={[s.painel, { backgroundColor: c["surface-100"], paddingBottom: margens.bottom + espaco["space-6"] }]}
      >
        <Text accessibilityRole="header" style={[estiloTexto("title"), { color: c.ink }]}>
          Abrir no mapa
        </Text>
        <Text style={[estiloTexto("body-strong"), { color: c.ink }]}>Google Maps</Text>
        {trechos.length > 1 ? (
          <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>
            O Google Maps aceita até {LIMITE_PARADAS_GOOGLE} paradas por rota. Sua viagem foi dividida em {trechos.length} trechos.
          </Text>
        ) : null}
        {trechos.map((trecho) => (
          <Button key={trecho.numero} block variant="secondary" onPress={() => Linking.openURL(trecho.url)}>
            {trechos.length > 1
              ? `Trecho ${trecho.numero}: ${trecho.de.split(",")[0]} → ${trecho.ate.split(",")[0]}`
              : "Abrir a rota"}
          </Button>
        ))}
        <Text style={[estiloTexto("body-strong"), { color: c.ink }]}>Waze</Text>
        <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>
          O Waze abre uma parada por vez.
        </Text>
        <Button block variant="secondary" onPress={abrirWaze}>
          {`Próxima: ${indiceWaze + 1}. ${lugarWaze.nome ?? "Lugar"}`}
        </Button>
        <Button block variant="ghost" onPress={onFechar}>
          Fechar
        </Button>
      </View>
    </Modal>
  );
}

type PropsBotao = {
  rotulo: string;
  leitura: string;
  onPress: () => void;
  disabled?: boolean;
  /** Sobre o item do roteiro (surface-200), o botão usa a superfície mais clara. */
  fundo?: "surface-100" | "surface-200";
};

function BotaoHora({ rotulo, leitura, onPress, disabled = false, fundo = "surface-200" }: PropsBotao) {
  const { c } = useCores();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={leitura}
      accessibilityState={{ disabled }}
      style={({ pressed }) => [
        s.botaoHora,
        { backgroundColor: pressed ? c["surface-300"] : c[fundo], opacity: disabled ? medida.desabilitado : 1 },
      ]}
    >
      <Text style={[estiloTexto("title"), { color: c.ink }]}>{rotulo}</Text>
    </Pressable>
  );
}

type PropsItem = {
  item: Card;
  posicao: number;
  /** Quantos lugares o roteiro tem, para saber se o item pode descer. */
  total: number;
  saida: number;
  /** A linha da IA dizendo por que o lugar está nessa posição. */
  porque?: string;
  /** Leva o item `passos` posições para baixo (negativo: para cima). */
  onMover: (passos: number) => void;
  onTirar: () => void;
};

function ItemRoteiro({ item, posicao, total, saida, porque, onMover, onTirar }: PropsItem) {
  const { c, sombra } = useCores();
  const deslocamento = useSharedValue(0);
  const arrastando = useSharedValue(false);
  const altura = useSharedValue(0);
  const nome = item.nome ?? "Lugar";
  // A agenda do coletor (dia e chegada) vale mais que a conta da tela, que não sabe dos pernoites.
  const chegada = minutosDe(item.chegada);
  const estimada =
    chegada != null && item.dia
      ? `~${hora(chegada)} do dia ${item.dia}`
      : item.horas_desde_saida != null
        ? horaEstimada(saida, item.horas_desde_saida)
        : null;
  const quando = [item.cidade, estimada, item.pernoite ? "pernoite" : null]
    .filter(Boolean)
    .join(" · ");
  const km = item.km_na_rota != null ? `KM ${numero(item.km_na_rota)}` : "";

  // Segurar e arrastar: cada altura de item, mais o espaço entre eles, é uma posição.
  const espacoEntreItens = espaco["space-2"];
  const gesto = Gesture.Pan()
    .activateAfterLongPress(SEGURAR_PARA_ARRASTAR_MS)
    .onStart(() => {
      arrastando.value = true;
    })
    .onUpdate((e) => {
      deslocamento.value = e.translationY;
    })
    .onEnd((e) => {
      const passo = altura.value + espacoEntreItens;
      const passos = passo > 0 ? Math.round(e.translationY / passo) : 0;
      if (passos !== 0) runOnJS(onMover)(passos);
    })
    .onFinalize(() => {
      arrastando.value = false;
      deslocamento.value = 0;
    });
  const sombraArrasto = sombra["shadow-2"];
  const movimento = useAnimatedStyle(() => ({
    transform: [{ translateY: deslocamento.value }],
    zIndex: arrastando.value ? 1 : 0,
    boxShadow: arrastando.value ? sombraArrasto : "none",
  }));

  return (
    <GestureDetector gesture={gesto}>
      <Animated.View
        onLayout={(e) => {
          altura.value = e.nativeEvent.layout.height;
        }}
        style={[s.item, { backgroundColor: c["surface-200"] }, movimento]}
      >
        <View
          accessible
          accessibilityLabel={[`${posicao}`, nome, quando, km, porque].filter(Boolean).join(", ")}
          style={s.linhaItem}
        >
          <View style={[s.numero, { backgroundColor: c.asfalto }]}>
            <Text style={[estiloTexto("km"), { color: c["on-asfalto"], fontFamily: fontes.placaForte }]}>{posicao}</Text>
          </View>
          <View style={s.info}>
            <Text style={[estiloTexto("body-strong"), { color: c.ink }]}>{nome}</Text>
            {quando ? <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>{quando}</Text> : null}
            {porque ? <Text style={[estiloTexto("body-s"), { color: c.ink }]}>{porque}</Text> : null}
          </View>
          <Text style={[estiloTexto("km"), { color: c["ink-muted"] }]}>{km}</Text>
        </View>
        <View style={s.acoesItem}>
          <BotaoHora
            rotulo="↑"
            leitura={`Subir ${nome}`}
            fundo="surface-100"
            disabled={posicao === 1}
            onPress={() => onMover(-1)}
          />
          <BotaoHora
            rotulo="↓"
            leitura={`Descer ${nome}`}
            fundo="surface-100"
            disabled={posicao === total}
            onPress={() => onMover(1)}
          />
          <BotaoHora rotulo="×" leitura={`Tirar ${nome} do roteiro`} fundo="surface-100" onPress={onTirar} />
        </View>
      </Animated.View>
    </GestureDetector>
  );
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  rolagem: { flexGrow: 1 },
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
  noites: { gap: espaco["space-2"], padding: espaco["space-3"], borderRadius: raio["radius-md"] },
  noite: { flexDirection: "row", alignItems: "center", gap: espaco["space-3"] },
  item: {
    gap: espaco["space-2"],
    padding: espaco["space-3"],
    borderRadius: raio["radius-md"],
  },
  linhaItem: { flexDirection: "row", alignItems: "center", gap: espaco["space-3"] },
  acoesItem: { flexDirection: "row", justifyContent: "flex-end", gap: espaco["space-2"] },
  numero: {
    width: medida.roteiroNumero,
    height: medida.roteiroNumero,
    borderRadius: raio["radius-pill"],
    alignItems: "center",
    justifyContent: "center",
  },
  info: { flex: 1, minWidth: 0 },
  rodape: {
    flexDirection: "row",
    gap: espaco["space-3"],
    paddingHorizontal: espaco["space-4"],
    paddingVertical: espaco["space-4"],
  },
  editar: { flex: 1 },
  abrirNoMapa: { flex: 2 },
  veu: { flex: 1 },
  painel: {
    gap: espaco["space-3"],
    padding: espaco["space-4"],
    borderTopLeftRadius: raio["radius-lg"],
    borderTopRightRadius: raio["radius-lg"],
  },
});
