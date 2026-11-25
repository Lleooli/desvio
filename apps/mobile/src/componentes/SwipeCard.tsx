import { duracao } from "@/duracao";
import { Image, Linking, StyleSheet, Text, View } from "react-native";
import { Gesture, GestureDetector, type GestureType } from "react-native-gesture-handler";
import { medida, espaco, estiloTexto, fontes, raio, tamanhoIcone, useCores } from "@/tema";
import { FundoCeu } from "./Ceu";
import { categorias, Chip, type Categoria } from "./Chip";
import { Icon } from "./Icon";
import { numero, Rating } from "./Rating";

export type Decisao = "bora" | "passo" | "favorito";

/** Os campos do card que a API devolve, já no formato do app. */
export type CardLugar = {
  id: string;
  nome: string;
  categoria?: Categoria;
  foto?: string | null;
  cidade?: string;
  uf?: string | null;
  nota?: number | null;
  avaliacoes?: number | null;
  /** km na rota. */
  km?: number | null;
  /** Horas desde a saída. */
  horas?: number | null;
  descricao?: string | null;
  /** URL ou @handle. */
  instagram?: string | null;
  /** true quando o @ veio de busca (instagram_origem = "busca"). */
  instagramProvavel?: boolean;
};

type Props = {
  card: CardLugar;
  /** Carimbo fixo; durante o arrasto quem desenha é a PilhaSwipe, com opacidade proporcional. */
  stamp?: Decisao | null;
  /** Card de trás da pilha: sem `shadow-card`, que é só do topo. */
  atras?: boolean;
  /** Gesto de toque de quem envolve o card: um toque no @ do Instagram abre só o link, sem disparar este. */
  toqueDeFora?: GestureType;
};

/** Extrai o @ de uma URL do Instagram ou de um "@handle"; outra coisa (um site qualquer) vira null. */
export function handleInstagram(instagram?: string | null): string | null {
  if (!instagram) return null;
  const achado = /instagram\.com\/([A-Za-z0-9_.]+)/.exec(instagram);
  if (achado) return achado[1];
  const handle = instagram.trim().replace(/^@/, "");
  return /^[A-Za-z0-9_.]{1,30}$/.test(handle) ? handle : null;
}

/** "KM 512" e "+6H48" (ou "+27H", "+45 MIN"): horas e minutos, nunca décimo de hora. */
export function textoKm(km: number, horas?: number | null) {
  return {
    km: `KM ${numero(km)}`,
    horas: horas != null ? `+${duracao(horas)}` : null,
  };
}

/** O card de um lugar na tela de swipe. Não arrasta sozinho: quem move é a PilhaSwipe. */
export function SwipeCard({ card, stamp, atras = false, toqueDeFora }: Props) {
  const { c, sombra } = useCores();
  const handle = handleInstagram(card.instagram);
  const km = card.km != null ? textoKm(card.km, card.horas) : null;
  // Sem app nem navegador para abrir o link, o toque não faz nada em vez de rejeitar a promise.
  const abrirInstagram = () => Linking.openURL(`https://instagram.com/${handle}`).catch(() => {});
  // O toque no link é um gesto, não onPress: assim ele bloqueia o toque de fora (o que abre a folha do lugar).
  const toqueNoLink = Gesture.Tap()
    .runOnJS(true)
    .onEnd((_e, terminou) => {
      if (terminou) abrirInstagram();
    });
  if (toqueDeFora) toqueNoLink.blocksExternalGesture(toqueDeFora);

  return (
    <View
      style={[
        s.card,
        { backgroundColor: c["surface-300"] },
        !atras && { boxShadow: sombra["shadow-card"] },
      ]}
    >
      <View style={s.recorte}>
        {card.foto ? (
          <Image source={{ uri: card.foto }} style={StyleSheet.absoluteFill} resizeMode="cover" />
        ) : (
          <SemFoto categoria={card.categoria} />
        )}
        <View
          aria-hidden
          style={[
            StyleSheet.absoluteFill,
            { experimental_backgroundImage: `linear-gradient(180deg, transparent 40%, ${c.scrim} 80%)` },
          ]}
        />

        <View style={s.topo}>
          {card.categoria ? <Chip categoria={card.categoria} onPhoto /> : <View />}
          {km ? (
            <View style={[s.km, { backgroundColor: c.vidro }]}>
              <Text style={[estiloTexto("km"), s.maiusculas, { color: c.ink }]}>{km.km}</Text>
              {km.horas ? <Text style={[estiloTexto("km"), s.horas, { color: c["ink-muted"] }]}>{km.horas}</Text> : null}
            </View>
          ) : null}
        </View>

        {stamp ? <Carimbo decisao={stamp} /> : null}

        <View style={s.corpo}>
          <Text accessibilityRole="header" style={[estiloTexto("display-l"), { color: c["on-scrim"] }]}>
            {card.nome}
          </Text>
          <View style={s.meta}>
            {card.cidade ? (
              <View style={s.lugar}>
                <Icon name="pin" size={tamanhoIcone.chip} color={c["on-scrim"]} />
                <Text style={[estiloTexto("body-s"), { color: c["on-scrim"] }]}>
                  {card.cidade + (card.uf ? `, ${card.uf}` : "")}
                </Text>
              </View>
            ) : null}
            <Rating nota={card.nota} avaliacoes={card.avaliacoes} onPhoto />
          </View>
          {card.descricao ? (
            <Text numberOfLines={2} style={[estiloTexto("body-s"), { color: c["on-scrim"] }]}>
              {card.descricao}
            </Text>
          ) : null}
          {handle ? (
            <GestureDetector gesture={toqueNoLink}>
              <Text
                accessibilityRole="link"
                accessibilityLabel={`Instagram ${handle}${card.instagramProvavel ? ", provável" : ""}`}
                // Leitor de tela: o toque duplo chega como "activate", não pelo gesto.
                accessibilityActions={[{ name: "activate" }]}
                onAccessibilityAction={(e) => {
                  if (e.nativeEvent.actionName === "activate") abrirInstagram();
                }}
                style={[estiloTexto("body-s"), s.instagram, { color: c["on-scrim"] }]}
              >
                @{handle}
                {card.instagramProvavel ? <Text style={s.provavel}> · provável</Text> : null}
              </Text>
            </GestureDetector>
          ) : null}
        </View>
      </View>
    </View>
  );
}

/** Céu com o ícone da categoria, no lugar da foto. Natureza e posto usam a variante placa. */
function SemFoto({ categoria }: { categoria?: Categoria }) {
  const { c } = useCores();
  const placa = categoria === "natureza" || categoria === "posto";
  const icone = categoria ? categorias[categoria].icon : "pin";

  return (
    <View aria-hidden style={[StyleSheet.absoluteFill, s.semFoto]}>
      <FundoCeu variante={placa ? "placa" : "faixa"} />
      <View style={s.iconeSemFoto}>
        <Icon name={icone} size={tamanhoIconeSemFoto} color={c.ink} />
      </View>
    </View>
  );
}

/** O carimbo do swipe: Bora à esquerda, Passo à direita, Favorito no meio. */
export function Carimbo({ decisao }: { decisao: Decisao }) {
  const { c } = useCores();
  const visual = {
    bora: { cor: c.placa, fundo: c["surface-200"], borda: c.placa, texto: "Bora", posicao: s.carimboBora },
    passo: { cor: c.ink, fundo: c["surface-200"], borda: c.ink, texto: "Passo", posicao: s.carimboPasso },
    favorito: { cor: c["on-faixa"], fundo: c.faixa, borda: c["on-faixa"], texto: "Favorito", posicao: s.carimboFavorito },
  }[decisao];

  return (
    <View pointerEvents="none" style={s.faixaCarimbo}>
      <Text
        accessibilityRole="text"
        style={[
          s.carimbo,
          visual.posicao,
          { color: visual.cor, backgroundColor: visual.fundo, borderColor: visual.borda },
        ]}
      >
        {visual.texto}
      </Text>
    </View>
  );
}

// Medidas do card em docs/design/design-system/components/bundle.css (.dv-card e .dv-stamp), via medida.
const tamanhoIconeSemFoto = medida.cardIconeSemFoto;
const tamanhoCarimbo = medida.cardCarimboTexto;

const s = StyleSheet.create({
  card: {
    width: "100%",
    maxWidth: medida.cardLarguraMaxima,
    aspectRatio: medida.cardProporcao,
    borderRadius: raio["radius-lg"],
  },
  recorte: { flex: 1, borderRadius: raio["radius-lg"], overflow: "hidden" },
  semFoto: { alignItems: "center" },
  iconeSemFoto: { position: "absolute", top: "38%", opacity: medida.cardIconeSemFotoOpacidade, transform: [{ translateY: -tamanhoIconeSemFoto / 2 }] },
  topo: {
    position: "absolute",
    top: espaco["space-4"],
    left: espaco["space-4"],
    right: espaco["space-4"],
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: espaco["space-2"],
  },
  km: {
    alignItems: "flex-end",
    paddingVertical: espaco["space-1"],
    paddingHorizontal: espaco["space-3"],
    borderRadius: raio["radius-sm"],
  },
  maiusculas: { textTransform: "uppercase" },
  horas: { fontSize: medida.cardHorasTexto, lineHeight: medida.cardHorasLinha },
  corpo: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingTop: espaco["space-4"],
    paddingHorizontal: espaco["space-4"],
    paddingBottom: espaco["space-6"],
    gap: espaco["space-2"],
  },
  meta: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", columnGap: espaco["space-3"], rowGap: espaco["space-2"] },
  lugar: { flexDirection: "row", alignItems: "center", gap: espaco["space-1"] },
  instagram: { fontFamily: fontes.sansForte, textDecorationLine: "underline", alignSelf: "flex-start" },
  provavel: { fontFamily: fontes.sans, opacity: medida.cardProvavelOpacidade },
  faixaCarimbo: { position: "absolute", top: medida.cardCarimboTopo, left: espaco["space-4"], right: espaco["space-4"], flexDirection: "row" },
  carimbo: {
    paddingVertical: espaco["space-1"],
    paddingHorizontal: espaco["space-3"],
    borderWidth: medida.cardCarimboBorda,
    borderRadius: raio["radius-sm"],
    fontFamily: fontes.placaForte,
    fontSize: tamanhoCarimbo,
    lineHeight: medida.cardCarimboLinha,
    letterSpacing: 0.08 * tamanhoCarimbo,
    textTransform: "uppercase",
    overflow: "hidden",
  },
  carimboBora: { marginRight: "auto", transform: [{ rotate: "-12deg" }] },
  carimboPasso: { marginLeft: "auto", transform: [{ rotate: "12deg" }] },
  carimboFavorito: { marginHorizontal: "auto", transform: [{ rotate: "-4deg" }] },
});
