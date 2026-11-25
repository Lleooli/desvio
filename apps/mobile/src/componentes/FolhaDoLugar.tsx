import { Image, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { Card } from "@/api";
import { textoHorarioHoje } from "@/horarioHoje";
import { espaco, estiloTexto, fontes, medida, raio, tamanhoIcone, useCores } from "@/tema";
import { Button } from "./Button";
import { FundoCeu } from "./Ceu";
import { categorias, Chip } from "./Chip";
import { useFoco } from "./foco";
import { Icon, type IconName } from "./Icon";
import { Rating } from "./Rating";
import { handleInstagram, textoKm } from "./SwipeCard";

type Props = {
  card: Card;
  onBora: () => void;
  onPasso: () => void;
  onFechar: () => void;
};

/** Abre um link fora do app; sem app nem navegador para abrir, o toque não faz nada. */
function abrir(url: string) {
  Linking.openURL(url).catch(() => {});
}

/**
 * A folha do lugar (HU11, canvas Lugar): foto ou céu no topo e, na folha, nome, km, nota,
 * descrição, endereço, horário de hoje, Instagram, as opções do `sobre` e o link para o
 * Google Maps. Bora e Passo ficam fixos embaixo.
 */
export function FolhaDoLugar({ card, onBora, onPasso, onFechar }: Props) {
  const { c, sombra } = useCores();
  const foco = useFoco();
  const handle = handleInstagram(card.instagram);
  const km = card.km_na_rota != null ? textoKm(card.km_na_rota, card.horas_desde_saida) : null;
  const horario = textoHorarioHoje(card.horario_hoje);
  const cidade = card.cidade ? card.cidade + (card.uf ? `, ${card.uf}` : "") : null;
  const endereco = [card.endereco, cidade].filter(Boolean).join(", ");
  const tipoPreco = [card.tipo, card.faixa_preco].filter(Boolean).join(" · ");
  const placa = card.categoria === "natureza" || card.categoria === "posto";

  return (
    <View style={[s.tela, { backgroundColor: c["surface-200"] }]}>
      <ScrollView contentContainerStyle={s.rolagem}>
        <View style={s.topo}>
          {card.foto ? (
            <Image source={{ uri: card.foto }} style={StyleSheet.absoluteFill} resizeMode="cover" />
          ) : (
            <View aria-hidden style={[StyleSheet.absoluteFill, s.semFoto]}>
              <FundoCeu variante={placa ? "placa" : "faixa"} />
              <View style={s.iconeSemFoto}>
                <Icon name={card.categoria ? categorias[card.categoria].icon : "pin"} size={medida.cardIconeSemFoto} color={c.ink} />
              </View>
            </View>
          )}
          <View style={s.barraTopo}>
            {card.categoria ? <Chip categoria={card.categoria} onPhoto /> : <View />}
            <Pressable
              onPress={onFechar}
              {...foco.eventos}
              accessibilityRole="button"
              accessibilityLabel="Fechar detalhes"
              style={[s.fechar, { backgroundColor: c.vidro }, foco.estilo]}
            >
              <Icon name="x" size={tamanhoIcone.nav} color={c.ink} />
            </Pressable>
          </View>
        </View>

        <View style={[s.folha, { backgroundColor: c["surface-200"], boxShadow: sombra["shadow-sheet"] }]}>
          <View aria-hidden style={[s.alca, { backgroundColor: c.line }]} />
          <View style={s.cabecalho}>
            <Text accessibilityRole="header" style={[estiloTexto("display-l"), s.nome, { color: c.ink }]}>
              {card.nome ?? "Lugar sem nome"}
            </Text>
            {km ? (
              <View style={[s.km, { backgroundColor: c.asfalto }]}>
                <Text style={[estiloTexto("km"), s.maiusculas, { color: c["on-asfalto"] }]}>{km.km}</Text>
                {km.horas ? <Text style={[estiloTexto("label"), { color: c["on-asfalto"] }]}>{km.horas}</Text> : null}
              </View>
            ) : null}
          </View>

          {card.nota != null || tipoPreco ? (
            <View style={s.meta}>
              <Rating nota={card.nota} avaliacoes={card.avaliacoes} />
              {tipoPreco ? <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>{tipoPreco}</Text> : null}
            </View>
          ) : null}

          {card.descricao ? <Text style={[estiloTexto("body"), { color: c.ink }]}>{card.descricao}</Text> : null}

          <View style={s.lista}>
            {endereco ? <Linha icone="pin" texto={endereco} /> : null}
            {horario ? <Linha icone="clock" texto={horario} /> : null}
            {handle ? (
              <Linha
                icone="at"
                texto={card.instagram_origem === "busca" ? `${handle} · provável` : handle}
                rotulo={`Instagram ${handle}${card.instagram_origem === "busca" ? ", provável" : ""}`}
                onPress={() => abrir(`https://instagram.com/${handle}`)}
              />
            ) : null}
          </View>

          {card.sobre?.length ? (
            <View style={s.sobre}>
              {card.sobre.map((opcao) => (
                <Chip key={opcao} label={opcao} />
              ))}
            </View>
          ) : null}

          {card.link_maps ? (
            <Text
              accessibilityRole="link"
              onPress={() => card.link_maps && abrir(card.link_maps)}
              style={[estiloTexto("body-strong"), s.link, { color: c.placa }]}
            >
              Abrir no Google Maps
            </Text>
          ) : null}
        </View>
      </ScrollView>

      <View style={[s.botoes, { backgroundColor: c["surface-200"] }]}>
        <View style={s.botao}>
          <Button variant="secondary" icon="x" block onPress={onPasso}>
            Passo
          </Button>
        </View>
        <View style={s.botao}>
          <Button icon="check" block onPress={onBora}>
            Bora
          </Button>
        </View>
      </View>
    </View>
  );
}

type LinhaProps = { icone: IconName; texto: string; rotulo?: string; onPress?: () => void };

/** Uma linha da lista de informações: ícone e texto; com `onPress`, o texto vira link. */
function Linha({ icone, texto, rotulo, onPress }: LinhaProps) {
  const { c } = useCores();
  return (
    <View style={s.linha}>
      <Icon name={icone} color={c.ink} />
      <Text
        accessibilityRole={onPress ? "link" : undefined}
        accessibilityLabel={rotulo}
        onPress={onPress}
        style={[estiloTexto("body"), s.textoLinha, { color: onPress ? c.placa : c.ink }, onPress && s.forte]}
      >
        {texto}
      </Text>
    </View>
  );
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  rolagem: { flexGrow: 1 },
  topo: { height: medida.lugarTopo, paddingTop: espaco["space-4"], paddingHorizontal: espaco["space-4"] },
  semFoto: { alignItems: "center", justifyContent: "center" },
  iconeSemFoto: { opacity: medida.cardIconeSemFotoOpacidade },
  barraTopo: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  fechar: {
    width: espaco.touch,
    height: espaco.touch,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: raio["radius-pill"],
  },
  folha: {
    flexGrow: 1,
    marginTop: -raio["radius-lg"],
    paddingTop: espaco["space-6"],
    paddingHorizontal: espaco["space-4"],
    paddingBottom: espaco["space-6"],
    borderTopLeftRadius: raio["radius-lg"],
    borderTopRightRadius: raio["radius-lg"],
    gap: espaco["space-3"],
  },
  alca: {
    position: "absolute",
    top: espaco["space-2"],
    alignSelf: "center",
    width: medida.alcaLargura,
    height: medida.alcaAltura,
    borderRadius: raio["radius-pill"],
  },
  cabecalho: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: espaco["space-3"] },
  nome: { flexShrink: 1 },
  km: {
    alignItems: "flex-end",
    paddingVertical: espaco["space-1"],
    paddingHorizontal: espaco["space-3"],
    borderRadius: raio["radius-sm"],
  },
  maiusculas: { textTransform: "uppercase" },
  meta: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", columnGap: espaco["space-4"], rowGap: espaco["space-2"] },
  lista: { gap: espaco["space-3"] },
  linha: { flexDirection: "row", alignItems: "center", gap: espaco["space-3"] },
  textoLinha: { flexShrink: 1 },
  forte: { fontFamily: fontes.sansForte },
  sobre: { flexDirection: "row", flexWrap: "wrap", gap: espaco["space-2"] },
  link: { alignSelf: "flex-start", paddingVertical: espaco["space-2"] },
  botoes: {
    flexDirection: "row",
    gap: espaco["space-3"],
    paddingHorizontal: espaco["space-4"],
    paddingTop: espaco["space-3"],
    paddingBottom: espaco["space-6"],
  },
  botao: { flex: 1 },
});
