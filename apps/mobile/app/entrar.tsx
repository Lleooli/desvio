import type { Session } from "@supabase/supabase-js";
import * as Linking from "expo-linking";
import { useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useEffect, useRef, useState } from "react";
import { Keyboard, KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Button } from "@/componentes/Button";
import { Ceu } from "@/componentes/Ceu";
import { Destaque } from "@/componentes/Destaque";
import { Icon } from "@/componentes/Icon";
import { TextField } from "@/componentes/TextField";
import {
  destinoDepoisDeEntrar,
  entrarComApple,
  entrarComGoogle,
  ErroEntrar,
  pedirLinkPorEmail,
  sessaoDoLink,
} from "@/sessao";
import { espaco, estiloTexto, medida, tamanhoIcone, useCores } from "@/tema";

// Onde os textos legais estão publicados; no .env do app. Sem a URL, o nome aparece sem link.
const LINK_TERMOS = process.env.EXPO_PUBLIC_TERMOS_URL;
const LINK_PRIVACIDADE = process.env.EXPO_PUBLIC_PRIVACIDADE_URL;

const EMAIL_VALIDO = /^\S+@\S+\.\S+$/;

// Linking.useURL relê o link que abriu o app a cada montagem; cada link só é tratado uma vez.
let ultimoLinkTratado: string | null = null;

function mensagemDe(erro: unknown): string {
  return erro instanceof ErroEntrar ? erro.message : new ErroEntrar("provedor").message;
}

/** Login com Google, Apple ou link por e-mail (canvas Entrar). Também recebe o link por e-mail aberto no celular. */
export default function Entrar() {
  const { c } = useCores();
  const router = useRouter();
  const margens = useSafeAreaInsets();
  const link = Linking.useURL();
  const [email, setEmail] = useState("");
  const [erroEmail, setErroEmail] = useState<string>();
  const [erro, setErro] = useState<string>();
  const [linkEnviado, setLinkEnviado] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const rolagem = useRef<ScrollView>(null);
  const tecladoAberto = useRef(false);

  // Com o teclado aberto, o campo de e-mail e o botão do link (no fim da tela) sobem para cima dele.
  // No Android o padding do KeyboardAvoidingView só chega num layout depois do evento, então a
  // rolagem se repete no onLayout do ScrollView, já com a área encolhida.
  useEffect(() => {
    const abriu = Keyboard.addListener("keyboardDidShow", () => {
      tecladoAberto.current = true;
      rolagem.current?.scrollToEnd();
    });
    const fechou = Keyboard.addListener("keyboardDidHide", () => {
      tecladoAberto.current = false;
    });
    return () => {
      abriu.remove();
      fechou.remove();
    };
  }, []);

  async function seguir(entrada: () => Promise<Session | null>) {
    setErro(undefined);
    setOcupado(true);
    try {
      const sessao = await entrada();
      if (sessao) router.replace(await destinoDepoisDeEntrar(sessao));
    } catch (e) {
      setErro(mensagemDe(e));
    } finally {
      setOcupado(false);
    }
  }

  // O link por e-mail abre o app aqui, com o código de acesso.
  useEffect(() => {
    if (!link || link === ultimoLinkTratado) return;
    ultimoLinkTratado = link;
    seguir(() => sessaoDoLink(link));
    // seguir muda a cada render; só um link novo deve disparar
  }, [link]);

  async function receberLink() {
    if (ocupado) return; // o Enter do teclado não passa pelo disabled do botão
    if (!EMAIL_VALIDO.test(email.trim())) {
      setErroEmail("Confira o e-mail: falta o @ ou o domínio.");
      return;
    }
    setErroEmail(undefined);
    setErro(undefined);
    setOcupado(true);
    try {
      await pedirLinkPorEmail(email);
      setLinkEnviado(true);
    } catch (e) {
      setErro(mensagemDe(e));
    } finally {
      setOcupado(false);
    }
  }

  function fechar() {
    if (router.canGoBack()) router.back();
    else router.replace("/boas-vindas");
  }

  const linkLegal = (rotulo: string, url: string | undefined) =>
    url ? (
      <Text accessibilityRole="link" style={{ color: c.placa }} onPress={() => WebBrowser.openBrowserAsync(url)}>
        {rotulo}
      </Text>
    ) : (
      rotulo
    );

  // "padding" também no Android: com a tela de ponta a ponta (Expo 57), a janela não encolhe sozinha com o teclado.
  return (
    <KeyboardAvoidingView style={[s.janela, { backgroundColor: c["surface-100"] }]} behavior="padding">
      <ScrollView
        ref={rolagem}
        style={{ backgroundColor: c["surface-100"] }}
        contentContainerStyle={[s.tela, { paddingBottom: margens.bottom + espaco["space-6"] }]}
        keyboardShouldPersistTaps="handled"
        onLayout={() => {
          if (tecladoAberto.current) rolagem.current?.scrollToEnd();
        }}
      >
        <Ceu serra>
          <View style={{ paddingTop: margens.top }}>
            <Pressable
              onPress={fechar}
              accessibilityRole="button"
              accessibilityLabel="Voltar"
              style={s.fechar}
            >
              <Icon name="x" size={tamanhoIcone.nav} color={c.ink} />
            </Pressable>
            <Text accessibilityRole="header" style={[estiloTexto("display-xl"), { color: c.ink }]}>
              Entre para guardar suas <Destaque>viagens</Destaque>
            </Text>
            <Text style={[estiloTexto("body"), s.texto, { color: c["ink-muted"] }]}>
              Seus roteiros e o que você curte ficam salvos em qualquer celular.
            </Text>
          </View>
        </Ceu>

        <View style={s.opcoes}>
          <Button block variant="secondary" disabled={ocupado} onPress={() => seguir(entrarComGoogle)}>
            Continuar com Google
          </Button>
          <Button block variant="secondary" disabled={ocupado} onPress={() => seguir(entrarComApple)}>
            Continuar com Apple
          </Button>
          <View style={s.divisor}>
            <View style={[s.linha, { backgroundColor: c.line }]} />
            <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>ou com e-mail</Text>
            <View style={[s.linha, { backgroundColor: c.line }]} />
          </View>
          <TextField
            label="Qual é o seu e-mail?"
            icon="at"
            value={email}
            onChangeText={(texto) => {
              setEmail(texto);
              setLinkEnviado(false);
            }}
            onSubmitEditing={receberLink}
            placeholder="voce@email.com"
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            autoCorrect={false}
            hint={
              linkEnviado
                ? "Mandamos o link para o seu e-mail. Abra no celular em até 15 minutos."
                : "Mandamos um link de acesso, sem senha."
            }
            erro={erroEmail}
          />
        </View>

        <View style={s.rodape}>
          {erro ? (
            <Text accessibilityRole="alert" style={[estiloTexto("body-s"), s.centro, { color: c.perigo }]}>
              {erro}
            </Text>
          ) : null}
          <Button block disabled={ocupado} onPress={receberLink}>
            {linkEnviado ? "Mandar outro link" : "Receber link de acesso"}
          </Button>
          <Text style={[estiloTexto("body-s"), s.centro, { color: c["ink-muted"] }]}>
            Ao continuar, você aceita os {linkLegal("Termos de uso", LINK_TERMOS)} e a{" "}
            {linkLegal("Política de privacidade", LINK_PRIVACIDADE)}.
          </Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  janela: { flex: 1 },
  tela: { flexGrow: 1 },
  fechar: {
    width: espaco.touch,
    height: espaco.touch,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: -espaco["space-3"],
    marginBottom: espaco["space-8"],
  },
  texto: { marginTop: espaco["space-3"] },
  opcoes: { gap: espaco["space-3"], paddingTop: espaco["space-2"], paddingHorizontal: espaco["space-4"] },
  divisor: { flexDirection: "row", alignItems: "center", gap: espaco["space-3"], marginVertical: espaco["space-1"] },
  linha: { flex: 1, height: medida.borda },
  rodape: { marginTop: "auto", gap: espaco["space-3"], paddingTop: espaco["space-6"], paddingHorizontal: espaco["space-4"] },
  centro: { textAlign: "center" },
});
