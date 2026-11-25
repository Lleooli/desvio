import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import type { Card, ParadaDaViagem, Viagem } from "@/api";
import { desfazerRegistro, lugaresDecididosNaFila, registrarDecisao } from "@/filaDecisoes";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, tipografia, useCores } from "@/tema";
import { Aviso } from "./Aviso";
import { Button } from "./Button";
import { useFoco } from "./foco";
import { Icon } from "./Icon";
import { naOrdemDaEstrada } from "./ParadasDaViagem";
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

type Props = {
  viagem: Viagem;
  /** A ordem da parada na viagem (o `:paradaId` da rota). */
  ordem: number;
};

/**
 * O swipe de uma parada (HU09, HU10): a pilha dos cards ainda sem decisão. Cada decisão
 * entra na fila do aparelho e vai ao coletor; Bora e Favorito mostram um toast com
 * Desfazer por 4 s, que devolve o card ao topo. No fim da pilha, volta às paradas ou
 * segue para a próxima parada com lugares.
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

  useEffect(() => {
    let valendo = true;
    lugaresDecididosNaFila().then((naFila) => {
      if (valendo) setCards(parada.cards.filter((card) => !naFila.has(card.id)));
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
    setCards((atuais) => [ultima.card, ...(atuais ?? [])]);
    setAceitos((n) => Math.max(0, n - 1));
    setUltima(null);
  };

  const naEstrada = naOrdemDaEstrada(viagem.paradas);
  const proxima = naEstrada.slice(naEstrada.indexOf(parada) + 1).find((p) => p.cards.length > 0);
  const irParaProxima = () =>
    proxima && router.replace({ pathname: "/viagens/[id]/paradas/[paradaId]", params: { id: viagem.id, paradaId: String(proxima.ordem) } });

  const topo = cards?.[0];
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
        </View>
        <Button variant="ghost" size="sm" onPress={() => voltarAsParadas(viagem.id)}>
          Pronto
        </Button>
      </View>

      {/* Com a pilha, os botões ficam embaixo e o toast logo acima deles; sem ela, o aviso no centro. */}
      <View style={[s.meio, topo ? s.meioComPilha : null]}>
        {cards === null ? (
          <ActivityIndicator color={c.placa} accessibilityLabel="Carregando os lugares" />
        ) : topo ? (
          <PilhaSwipe cards={cards.map(paraCardLugar)} onDecisao={decidir} />
        ) : (
          <View style={s.fim}>
            <Text style={[estiloTexto("body"), s.textoFim, { color: c.ink }]}>
              {`Você viu todos os lugares de ${parada.nome}.`}
            </Text>
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
            onPress={() => router.push({ pathname: "/lugares/[lugarId]", params: { lugarId: topo.id } })}
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
  titulo: { flexShrink: 1, alignItems: "center" },
  km: { textTransform: "uppercase" },
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
