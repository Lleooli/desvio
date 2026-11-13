import { Image, Linking, StyleSheet, Text, View } from "react-native";
import { espaco, estiloTexto, fontes, raio, tamanhoIcone, useCores } from "@/tema";
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
  /** km na rota; só no modo carro. */
  km?: number | null;
  /** Horas desde a saída; só no modo carro. */
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
};

/** Extrai o @ de uma URL do Instagram ou de um "@handle". */
export function handleInstagram(instagram?: string | null): string | null {
  if (!instagram) return null;
  const achado = /instagram\.com\/([A-Za-z0-9_.]+)/.exec(instagram);
  return achado ? achado[1] : instagram.replace(/^@/, "");
}

/** "KM 512" e "+6,8H" (ou "+27H"), no padrão brasileiro. */
export function textoKm(km: number, horas?: number | null) {
  return {
    km: `KM ${numero(km)}`,
    horas: horas != null ? `+${numero(horas, horas % 1 ? 1 : 0)}H` : null,
  };
}

/** O card de um lugar na tela de swipe. Não arrasta sozinho: quem move é a PilhaSwipe. */
export function SwipeCard({ card, stamp, atras = false }: Props) {
  const { c, sombra } = useCores();
  const handle = handleInstagram(card.instagram);
  const km = card.km != null ? textoKm(card.km, card.horas) : null;

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
            <Text
              accessibilityRole="link"
              accessibilityLabel={`Instagram ${handle}${card.instagramProvavel ? ", provável" : ""}`}
              onPress={() => Linking.openURL(`https://instagram.com/${handle}`)}
              style={[estiloTexto("body-s"), s.instagram, { color: c["on-scrim"] }]}
            >
              @{handle}
              {card.instagramProvavel ? <Text style={s.provavel}> · provável</Text> : null}
            </Text>
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
  // Os mesmos quatro brilhos do Céu no design system (bundle.css, .dv-ceu).
  const ceu = [
    `radial-gradient(64% 74% at 0% 0%, ${c["ceu-azul"]} 0%, transparent 64%)`,
    placa
      ? `radial-gradient(56% 66% at 100% 0%, ${c["ceu-placa"]} 0%, transparent 64%)`
      : `radial-gradient(54% 64% at 100% 0%, ${c["ceu-claro"]} 0%, transparent 62%)`,
    `radial-gradient(62% 70% at 0% 100%, ${c["ceu-sol"]} 0%, transparent 66%)`,
    placa
      ? `radial-gradient(52% 62% at 100% 100%, ${c["ceu-claro"]} 0%, transparent 62%)`
      : `radial-gradient(56% 66% at 100% 100%, ${c["ceu-faixa"]} 0%, transparent 64%)`,
  ].join(", ");
  const icone = categoria ? categorias[categoria].icon : "pin";

  return (
    <View
      aria-hidden
      style={[StyleSheet.absoluteFill, s.semFoto, { backgroundColor: c["ceu-base"], experimental_backgroundImage: ceu }]}
    >
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

// Medidas do card em docs/design/design-system/components/bundle.css (.dv-card e .dv-stamp).
const tamanhoIconeSemFoto = 72;
const larguraMaxima = 380;
const topoCarimbo = 96;
const bordaCarimbo = 3;
const tamanhoCarimbo = 34;
const alturaCarimbo = 38;
const textoHoras = { tamanho: 13, altura: 16 };

const s = StyleSheet.create({
  card: {
    width: "100%",
    maxWidth: larguraMaxima,
    aspectRatio: 3 / 4.3,
    borderRadius: raio["radius-lg"],
  },
  recorte: { flex: 1, borderRadius: raio["radius-lg"], overflow: "hidden" },
  semFoto: { alignItems: "center" },
  iconeSemFoto: { position: "absolute", top: "38%", opacity: 0.35, transform: [{ translateY: -tamanhoIconeSemFoto / 2 }] },
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
  horas: { fontSize: textoHoras.tamanho, lineHeight: textoHoras.altura },
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
  provavel: { fontFamily: fontes.sans, opacity: 0.85 },
  faixaCarimbo: { position: "absolute", top: topoCarimbo, left: espaco["space-4"], right: espaco["space-4"], flexDirection: "row" },
  carimbo: {
    paddingVertical: espaco["space-1"],
    paddingHorizontal: espaco["space-3"],
    borderWidth: bordaCarimbo,
    borderRadius: raio["radius-sm"],
    fontFamily: fontes.placaForte,
    fontSize: tamanhoCarimbo,
    lineHeight: alturaCarimbo,
    letterSpacing: 0.08 * tamanhoCarimbo,
    textTransform: "uppercase",
    overflow: "hidden",
  },
  carimboBora: { marginRight: "auto", transform: [{ rotate: "-12deg" }] },
  carimboPasso: { marginLeft: "auto", transform: [{ rotate: "12deg" }] },
  carimboFavorito: { marginHorizontal: "auto", transform: [{ rotate: "-4deg" }] },
});
