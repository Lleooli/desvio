import { router } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { Card, ParadaDaViagem, Viagem } from "@/api";
import { abrirFolhaDoLugar } from "@/folhaDoLugar";
import { desfazerRegistro, lugaresDecididosNaFila, registrarDecisao } from "@/filaDecisoes";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, tipografia, useCores } from "@/tema";
import { Aviso } from "./Aviso";
import { Button } from "./Button";
import { categorias, Chip, type Categoria } from "./Chip";
import { useFoco } from "./foco";
import { Icon } from "./Icon";
import { AindaBuscando, naOrdemDaEstrada } from "./ParadasDaViagem";
import { PilhaSwipe } from "./PilhaSwipe";
import { numero } from "./Rating";
import type { CardLugar, Decisao } from "./SwipeCard";
import { Toast } from "./Toast";

const DURACAO_DESFAZER_MS = 4000;
// Altura dos SwipeActions (padding, botão e rótulo): o toast fica logo acima deles, sobre o card.
const ALTURA_BOTOES = 2 * espaco["space-4"] + medida.botaoSwipe + espaco["space-1"] + tipografia.label.altura;

/** O card da API no formato do SwipeCard. */
function paraCardLugar(card: Card): CardLugar {
  return {
    id: card.id,
    nome: card.nome ?? "Lugar sem nome",
    categoria: card.categoria,
    foto: card.foto,
    cidade: card.cidade,
    uf: card.uf,
    nota: card.nota,
    avaliacoes: card.avaliacoes,
    km: card.km_na_rota,
    horas: card.horas_desde_saida,
    descricao: card.descricao,
    instagram: card.instagram,
    instagramProvavel: card.instagram_origem === "busca",
  };
}

/**
 * Junta à pilha os cards da parada que ela ainda não tem, no fim e na ordem em que vieram.
 * Fica de fora o que já está na pilha e o que está em `fora` (já decidido), então nenhum
 * card aparece duas vezes, nem quando a viagem chega de novo com os lugares do Google.
 * Sem nada novo, devolve a mesma pilha.
 */
export function juntarNaPilha(pilha: Card[], daParada: Card[], fora: ReadonlySet<string>): Card[] {
  const vistos = new Set([...fora, ...pilha.map((card) => card.id)]);
  const novos = daParada.filter((card) => {
    if (vistos.has(card.id)) return false;
    vistos.add(card.id);
    return true;
  });
  return novos.length > 0 ? [...pilha, ...novos] : pilha;
}

/**
 * Os cards da parada na ordem da pilha: na estadia (a cidade onde a pessoa dorme), os de
 * hospedagem primeiro, sem mudar a ordem entre eles; nas outras, como vieram.
 */
export function naOrdemDaPilha(parada: Pick<ParadaDaViagem, "tipo" | "cards">): Card[] {
  if (parada.tipo !== "estadia") return parada.cards;
  const hotel = (card: Card) => (card.categoria === "hospedagem" ? 0 : 1);
  return [...parada.cards].sort((a, b) => hotel(a) - hotel(b));
}

/** "Onde dormir no dia 2": o selo da parada de estadia. */
export function ondeDormir(parada: Pick<ParadaDaViagem, "dia">): string {
  return parada.dia ? `Onde dormir no dia ${parada.dia}` : "Onde dormir";
}

type Props = {
  viagem: Viagem;
  /** A ordem da parada na viagem (o `:paradaId` da rota). */
  ordem: number;
};

/**
 * O swipe de uma parada (HU09, HU10): a pilha dos cards ainda sem decisão. Cada decisão
 * entra na fila do aparelho e vai ao coletor; Bora e Favorito mostram um toast com
 * Desfazer por 4 s, que devolve o card ao topo. No fim da pilha, volta às paradas ou
 * segue para a próxima parada com lugares. Os chips do topo filtram a pilha por categoria
 * (HU12); o filtro mora na pilha, que é montada de novo a cada parada, então trocar de
 * parada limpa o filtro. Na cidade de estadia, os hotéis vêm primeiro, com o selo "Onde
 * dormir no dia N" (issue #104).
 */
export function SwipeDaParada({ viagem, ordem }: Props) {
  const parada = viagem.paradas.find((p) => p.ordem === ordem);
  if (!parada) {
    return <Aviso mensagem="Essa parada não existe mais nesta viagem." acao="Ver paradas" onAcao={() => voltarAsParadas(viagem.id)} />;
  }
  return <Pilha key={`${viagem.id}:${ordem}`} viagem={viagem} parada={parada} />;
}

function voltarAsParadas(viagemId: string) {
  if (router.canGoBack()) router.back();
  else router.replace({ pathname: "/viagens/[id]/paradas", params: { id: viagemId } });
}

function Pilha({ viagem, parada }: { viagem: Viagem; parada: ParadaDaViagem }) {
  const { c } = useCores();
  const foco = useFoco();
  // null enquanto lê a fila do aparelho: decisão que ainda não chegou ao coletor não volta à pilha.
  const [cards, setCards] = useState<Card[] | null>(null);
  const [aceitos, setAceitos] = useState(parada.progresso.aceitos);
  const [ultima, setUltima] = useState<{ card: Card; decisao: Decisao } | null>(null);
  // Vazio mostra todas as categorias.
  const [filtro, setFiltro] = useState<ReadonlySet<Categoria>>(new Set());

  // Os lugares decididos nesta pilha. Uma viagem buscada antes de a decisão chegar ao
  // coletor ainda traz o card; com este conjunto ele não volta.
  const decididos = useRef(new Set<string>());

  // A viagem chega de novo a cada 10 s enquanto a busca roda: os cards novos (do Google)
  // entram no fim da pilha, sem mexer na ordem nem no card do topo.
  useEffect(() => {
    let valendo = true;
    lugaresDecididosNaFila().then((naFila) => {
      if (!valendo) return;
      const fora = new Set([...naFila, ...decididos.current]);
      setCards((atuais) => juntarNaPilha(atuais ?? [], naOrdemDaPilha(parada), fora));
    });
    return () => {
      valendo = false;
    };
  }, [parada]);

  useEffect(() => {
    if (!ultima) return;
    const relogio = setTimeout(() => setUltima(null), DURACAO_DESFAZER_MS);
    return () => clearTimeout(relogio);
  }, [ultima]);

  const decidir = (lugar: CardLugar, decisao: Decisao) => {
    const card = cards?.find((outro) => outro.id === lugar.id);
    if (!card) return;
    setCards((atuais) => atuais?.filter((outro) => outro.id !== card.id) ?? null);
    decididos.current.add(card.id);
    registrarDecisao(card, decisao, { viagem: viagem.id, parada: parada.ordem });
    if (decisao === "passo") {
      setUltima(null);
    } else {
      setAceitos((n) => n + 1);
      setUltima({ card, decisao });
    }
  };

  const desfazer = () => {
    if (!ultima) return;
    desfazerRegistro(ultima.card.id);
    decididos.current.delete(ultima.card.id);
    setCards((atuais) => [ultima.card, ...(atuais ?? []).filter((outro) => outro.id !== ultima.card.id)]);
    setAceitos((n) => Math.max(0, n - 1));
    setUltima(null);
  };

  // A folha decide pelo mesmo caminho do swipe: o card sai da pilha e o toast aparece.
  const abrirDetalhe = (lugar: CardLugar) => {
    const card = cards?.find((outro) => outro.id === lugar.id);
    if (card) abrirFolhaDoLugar(card, (decisao) => decidir(lugar, decisao));
  };

  const naEstrada = naOrdemDaEstrada(viagem.paradas);
  const proxima = naEstrada.slice(naEstrada.indexOf(parada) + 1).find((p) => p.cards.length > 0);
  const irParaProxima = () =>
    proxima && router.replace({ pathname: "/viagens/[id]/paradas/[paradaId]", params: { id: viagem.id, paradaId: String(proxima.ordem) } });

  // Só as categorias que a parada tem, na ordem do design system; com uma só, filtrar não muda nada.
  const categoriasDaParada = (Object.keys(categorias) as Categoria[]).filter((categoria) =>
    parada.cards.some((card) => card.categoria === categoria),
  );
  const alternar = (categoria: Categoria) =>
    setFiltro((atual) => {
      const novo = new Set(atual);
      if (!novo.delete(categoria)) novo.add(categoria);
      return novo;
    });
  const visiveis =
    filtro.size === 0 ? cards : (cards?.filter((card) => card.categoria && filtro.has(card.categoria)) ?? null);

  const topo = visiveis?.[0];
  const cidade = parada.uf ? `${parada.nome}, ${parada.uf}` : parada.nome;
  const contagem = `${numero(aceitos)} de ${numero(parada.progresso.total)} escolhidos`;

  return (
    <View style={s.tela}>
      <View style={s.cabecalho}>
        <Pressable
          onPress={() => voltarAsParadas(viagem.id)}
          {...foco.eventos}
          accessibilityRole="button"
          accessibilityLabel="Voltar para as paradas"
          style={[s.fechar, foco.estilo]}
        >
          <Icon name="x" size={tamanhoIcone.nav} color={c.ink} />
        </Pressable>
        <View style={s.titulo}>
          <Text accessibilityRole="header" style={[estiloTexto("title"), { color: c.ink }]}>
            {cidade}
          </Text>
          <Text style={[estiloTexto("km"), s.km, { color: c["ink-muted"] }]}>
            {parada.km_na_rota != null ? `KM ${numero(parada.km_na_rota)} · ${contagem}` : contagem}
          </Text>
          {parada.tipo === "estadia" ? (
            <View style={[s.selo, { backgroundColor: c.faixa }]}>
              <Icon name="bed" size={tamanhoIcone.padrao} color={c["on-faixa"]} />
              <Text style={[estiloTexto("label"), { color: c["on-faixa"] }]}>{ondeDormir(parada)}</Text>
            </View>
          ) : null}
        </View>
        <Button variant="ghost" size="sm" onPress={() => voltarAsParadas(viagem.id)}>
          Pronto
        </Button>
      </View>

      {categoriasDaParada.length > 1 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.filtros} contentContainerStyle={s.filtrosConteudo}>
          {categoriasDaParada.map((categoria) => (
            <Chip key={categoria} categoria={categoria} selected={filtro.has(categoria)} onPress={() => alternar(categoria)} />
          ))}
        </ScrollView>
      ) : null}

      {/* Com a pilha, os botões ficam embaixo e o toast logo acima deles; sem ela, o aviso no centro. */}
      <View style={[s.meio, topo ? s.meioComPilha : null]}>
        {visiveis === null ? (
          <ActivityIndicator color={c.placa} accessibilityLabel="Carregando os lugares" />
        ) : topo ? (
          <PilhaSwipe cards={visiveis.map(paraCardLugar)} onDecisao={decidir} onAbrir={abrirDetalhe} />
        ) : cards && cards.length > 0 ? (
          <View style={s.fim}>
            <Text style={[estiloTexto("body"), s.textoFim, { color: c.ink }]}>
              {`Você viu todos os lugares dessa categoria em ${parada.nome}.`}
            </Text>
            <Button onPress={() => setFiltro(new Set())}>Ver todos</Button>
          </View>
        ) : (
          <View style={s.fim}>
            <Text style={[estiloTexto("body"), s.textoFim, { color: c.ink }]}>
              {viagem.status === "buscando"
                ? `Você viu os lugares que já chegaram de ${parada.nome}.`
                : `Você viu todos os lugares de ${parada.nome}.`}
            </Text>
            {viagem.status === "buscando" ? <AindaBuscando /> : null}
            {proxima ? (
              <Button icon="route" onPress={irParaProxima}>
                Próxima parada
              </Button>
            ) : null}
            <Button variant={proxima ? "secondary" : "primary"} onPress={() => voltarAsParadas(viagem.id)}>
              Ver paradas
            </Button>
          </View>
        )}
        {ultima ? (
          <View pointerEvents="box-none" style={s.toast}>
            <Toast icon={ultima.decisao === "favorito" ? "star" : "check"} acao="Desfazer" onAcao={desfazer}>
              {ultima.decisao === "favorito"
                ? `${ultima.card.nome ?? "O lugar"} virou favorito`
                : `${ultima.card.nome ?? "O lugar"} entrou no roteiro`}
            </Toast>
          </View>
        ) : null}
      </View>

      <View style={s.rodape}>
        {topo ? (
          <Button
            variant="ghost"
            size="sm"
            onPress={() => abrirDetalhe(paraCardLugar(topo))}
          >
            Ver detalhes do lugar
          </Button>
        ) : null}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  cabecalho: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: espaco["space-2"],
    paddingHorizontal: espaco["space-3"],
    paddingVertical: espaco["space-2"],
  },
  fechar: {
    width: espaco.touch,
    height: espaco.touch,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: raio["radius-pill"],
  },
  titulo: { flexShrink: 1, alignItems: "center", gap: espaco["space-1"] },
  selo: {
    flexDirection: "row",
    alignItems: "center",
    gap: espaco["space-1"],
    paddingHorizontal: espaco["space-2"],
    paddingVertical: espaco["space-1"],
    borderRadius: raio["radius-pill"],
  },
  km: { textTransform: "uppercase" },
  filtros: { flexGrow: 0 },
  filtrosConteudo: { gap: espaco["space-2"], paddingHorizontal: espaco["space-4"], paddingTop: espaco["space-1"], paddingBottom: espaco["space-3"] },
  meio: { flex: 1, justifyContent: "center" },
  meioComPilha: { justifyContent: "flex-end" },
  fim: { alignItems: "center", gap: espaco["space-4"], padding: espaco["space-6"] },
  textoFim: { textAlign: "center" },
  toast: {
    position: "absolute",
    left: espaco["space-4"],
    right: espaco["space-4"],
    bottom: ALTURA_BOTOES + espaco["space-2"],
    alignItems: "center",
  },
  rodape: { alignItems: "center", minHeight: espaco.touch, paddingBottom: espaco["space-4"] },
});
