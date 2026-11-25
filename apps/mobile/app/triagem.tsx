import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { mensagemDeErro, pularTriagem, responderTriagem, type PassoTriagem, type RespostaTriagem } from "@/api";
import { Button } from "@/componentes/Button";
import { Chip } from "@/componentes/Chip";
import { TextField } from "@/componentes/TextField";
import { espaco, estiloTexto, medida, raio, useCores } from "@/tema";

// O mesmo teto do coletor (ia.MAX_PERGUNTAS); quem garante que não passa dele é o coletor.
const MAX_PERGUNTAS = 5;

function dicaDo(passo: PassoTriagem): string {
  if (passo.livre) return "Escreva do seu jeito ou toque numa sugestão.";
  return passo.multi ? "Escolha quantas quiser." : "Toque em uma opção.";
}

/** O leitor de tela ouve a pergunta, a dica e as opções assim que ela chega. */
function anunciar(passo: PassoTriagem): void {
  if (!passo.pergunta) return;
  const opcoes = passo.opcoes.length ? ` Opções: ${passo.opcoes.join(", ")}.` : "";
  AccessibilityInfo.announceForAccessibility(`${passo.pergunta} ${dicaDo(passo)}${opcoes}`);
}

/** Balão da conversa: o da IA à esquerda, com o selo, e o da pessoa à direita. */
function Balao({ ia, texto }: { ia: boolean; texto: string }) {
  const { c, sombra } = useCores();
  if (!ia) {
    return (
      <View style={s.linhaEu}>
        <Text style={[estiloTexto("body-strong"), s.balaoEu, { backgroundColor: c.ink, color: c["surface-100"] }]}>
          {texto}
        </Text>
      </View>
    );
  }
  return (
    <View style={s.linhaIa}>
      <View style={[s.selo, { backgroundColor: c.placa }]} accessible={false} importantForAccessibility="no-hide-descendants">
        <Text style={[estiloTexto("label"), { color: c["on-placa"] }]}>IA</Text>
      </View>
      <Text
        accessibilityLabel={`IA: ${texto}`}
        style={[estiloTexto("body"), s.balaoIa, { backgroundColor: c["surface-200"], color: c.ink, boxShadow: sombra["shadow-1"] }]}
      >
        {texto}
      </Text>
    </View>
  );
}

/**
 * Triagem em conversa (canvas Triagem): até 5 perguntas, e a resposta vira o perfil de gosto.
 * Aberta pelo perfil (`refazer=1`, HU03), as respostas novas substituem as antigas e a tela volta ao perfil.
 */
export default function Triagem() {
  const { c, sombra } = useCores();
  const router = useRouter();
  const refazendo = useLocalSearchParams<{ refazer?: string }>().refazer === "1";
  const margens = useSafeAreaInsets();
  const rolagem = useRef<ScrollView>(null);
  const [respostas, setRespostas] = useState<RespostaTriagem[]>([]);
  const [passo, setPasso] = useState<PassoTriagem>();
  const [escolhidas, setEscolhidas] = useState<string[]>([]);
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState<string>();
  const [ocupado, setOcupado] = useState(false);

  async function pedirPasso(lista: RespostaTriagem[]) {
    // A resposta entra na conversa já; se a rede falhar, "Tentar de novo" manda a mesma lista
    // e "Pular" guarda inclusive ela.
    setRespostas(lista);
    setPasso(undefined);
    setErro(undefined);
    setOcupado(true);
    try {
      const proximo = await responderTriagem(lista);
      setPasso(proximo);
      setEscolhidas([]);
      setTexto("");
      anunciar(proximo);
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }

  useEffect(() => {
    pedirPasso([]);
  }, []);

  function responder(resposta: string) {
    if (!passo?.pergunta || !resposta.trim() || ocupado) return;
    pedirPasso([...respostas, { pergunta: passo.pergunta, resposta: resposta.trim() }]);
  }

  function alternar(opcao: string) {
    setEscolhidas(escolhidas.includes(opcao) ? escolhidas.filter((x) => x !== opcao) : [...escolhidas, opcao]);
  }

  async function pular() {
    // Ao refazer, pular nunca grava: sem a triagem concluída não há resumo novo, e gravar o pulo
    // apagaria o resumo antigo (inclusive um corrigido à mão no perfil).
    if (refazendo) {
      router.back();
      return;
    }
    try {
      await pularTriagem(respostas);
    } catch {
      // Sem rede, as respostas não são guardadas, mas a pessoa não fica presa na triagem:
      // ela pode refazer as perguntas pelo perfil.
    }
    router.replace("/viagens");
  }

  const fim = !!passo?.fim;
  const respondidas = Math.min(respostas.length, MAX_PERGUNTAS);
  const progressoTexto = fim ? "pronto" : `${Math.min(respondidas + 1, MAX_PERGUNTAS)} de ${MAX_PERGUNTAS}`;
  const resumo = passo?.resumo ?? "Pronto! Já dá para começar. Você pode ajustar seu gosto quando quiser no perfil.";

  return (
    <KeyboardAvoidingView
      style={[s.tela, { backgroundColor: c["surface-100"] }]}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={[s.topo, { paddingTop: margens.top + espaco["space-3"] }]}>
        <View style={s.linhaTopo}>
          <Text style={[estiloTexto("label"), s.maiusculas, { color: c["ink-muted"] }]}>
            Conhecendo você · {progressoTexto}
          </Text>
          {fim ? null : (
            <Pressable
              onPress={pular}
              accessibilityRole="button"
              accessibilityLabel="Pular"
              accessibilityHint={
                refazendo
                  ? "Volta ao perfil sem mudar o seu gosto"
                  : "Guarda o que você já respondeu e vai para suas viagens"
              }
              style={s.pular}
            >
              <Text style={[estiloTexto("body-strong"), { color: c.placa }]}>Pular</Text>
            </Pressable>
          )}
        </View>
        <View
          accessibilityRole="progressbar"
          accessibilityLabel="Progresso das perguntas"
          accessibilityValue={{ min: 0, max: MAX_PERGUNTAS, now: fim ? MAX_PERGUNTAS : respondidas }}
          style={[s.barra, { backgroundColor: c["surface-300"] }]}
        >
          <View
            style={[
              s.preenchido,
              { width: `${((fim ? MAX_PERGUNTAS : respondidas) / MAX_PERGUNTAS) * 100}%`, backgroundColor: c.placa },
            ]}
          />
        </View>
      </View>

      <ScrollView
        ref={rolagem}
        style={s.conversa}
        contentContainerStyle={s.mensagens}
        onContentSizeChange={() => rolagem.current?.scrollToEnd({ animated: true })}
      >
        {respostas.map((r, i) => (
          <View key={i} style={s.par}>
            <Balao ia texto={r.pergunta} />
            <Balao ia={false} texto={r.resposta} />
          </View>
        ))}
        {passo?.pergunta ? <Balao ia texto={passo.pergunta} /> : null}
        {fim ? <Balao ia texto={resumo} /> : null}
      </ScrollView>

      <View
        style={[
          s.painel,
          { backgroundColor: c["surface-200"], boxShadow: sombra["shadow-sheet"], paddingBottom: margens.bottom + espaco["space-6"] },
        ]}
      >
        {erro ? (
          <>
            <Text accessibilityRole="alert" style={[estiloTexto("body-s"), { color: c.perigo }]}>
              {erro}
            </Text>
            <Button block disabled={ocupado} onPress={() => pedirPasso(respostas)}>
              Tentar de novo
            </Button>
          </>
        ) : null}

        {!erro && passo && !fim ? (
          <>
            <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>{dicaDo(passo)}</Text>
            {passo.opcoes.length ? (
              <View style={s.chips}>
                {passo.opcoes.map((opcao) => (
                  <Chip
                    key={opcao}
                    label={opcao}
                    selected={passo.multi && !passo.livre && escolhidas.includes(opcao)}
                    onPress={() => {
                      if (passo.livre) setTexto(opcao);
                      else if (passo.multi) alternar(opcao);
                      else responder(opcao);
                    }}
                  />
                ))}
              </View>
            ) : null}
            {passo.livre ? (
              <>
                <TextField
                  label="Escreva do seu jeito"
                  placeholder="Ex.: sempre paro para tomar café"
                  value={texto}
                  onChangeText={setTexto}
                  onSubmitEditing={() => responder(texto)}
                  returnKeyType="send"
                />
                <Button block disabled={ocupado || !texto.trim()} onPress={() => responder(texto)}>
                  Enviar
                </Button>
              </>
            ) : passo.multi ? (
              <Button block disabled={ocupado || escolhidas.length === 0} onPress={() => responder(escolhidas.join(", "))}>
                Continuar
              </Button>
            ) : null}
          </>
        ) : null}

        {fim && refazendo ? (
          <Button block onPress={() => router.back()}>
            Voltar ao perfil
          </Button>
        ) : null}
        {fim && !refazendo ? (
          <Button block onPress={() => router.replace("/viagens/nova")}>
            Planejar minha primeira viagem
          </Button>
        ) : null}
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  topo: { gap: espaco["space-3"], paddingHorizontal: espaco["space-4"], paddingBottom: espaco["space-3"] },
  linhaTopo: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  maiusculas: { textTransform: "uppercase" },
  pular: { minHeight: espaco.touch, minWidth: espaco.touch, alignItems: "flex-end", justifyContent: "center" },
  barra: { height: medida.barraTriagem, borderRadius: raio["radius-pill"], overflow: "hidden" },
  preenchido: { height: "100%", borderRadius: raio["radius-pill"] },
  conversa: { flex: 1 },
  mensagens: { gap: espaco["space-3"], paddingHorizontal: espaco["space-4"], paddingTop: espaco["space-2"], paddingBottom: espaco["space-4"] },
  par: { gap: espaco["space-3"] },
  linhaIa: { flexDirection: "row", alignItems: "flex-end", gap: espaco["space-2"], maxWidth: "92%" },
  linhaEu: { flexDirection: "row", justifyContent: "flex-end", marginLeft: "auto", maxWidth: "85%" },
  selo: {
    width: medida.seloIa,
    height: medida.seloIa,
    borderRadius: raio["radius-pill"],
    alignItems: "center",
    justifyContent: "center",
  },
  balaoIa: {
    flexShrink: 1,
    paddingVertical: espaco["space-3"],
    paddingHorizontal: espaco["space-4"],
    borderRadius: raio["radius-md"],
    borderBottomLeftRadius: medida.cantoBalao,
    overflow: "hidden",
  },
  balaoEu: {
    paddingVertical: espaco["space-2"],
    paddingHorizontal: espaco["space-4"],
    borderRadius: raio["radius-md"],
    borderBottomRightRadius: medida.cantoBalao,
    overflow: "hidden",
  },
  painel: {
    gap: espaco["space-3"],
    paddingTop: espaco["space-3"],
    paddingHorizontal: espaco["space-4"],
    borderTopLeftRadius: raio["radius-lg"],
    borderTopRightRadius: raio["radius-lg"],
  },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: espaco["space-2"] },
});
