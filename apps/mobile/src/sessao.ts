/**
 * Sessão do Supabase Auth: entrar com Google, Apple ou link por e-mail, sessão guardada no
 * aparelho e `access_token` em toda chamada à API. As telas nunca falam direto com o Supabase.
 */
import "react-native-url-polyfill/auto"; // o URL do React Native não tem o que o supabase-js usa
import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient, type Session } from "@supabase/supabase-js";
import * as AppleAuthentication from "expo-apple-authentication";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { useSyncExternalStore } from "react";
import { AppState, Platform } from "react-native";
import { definirFonteToken } from "@/api";
import { esquecerTokenDePush, registrarTokenDePush } from "@/push";

// No .env do app: EXPO_PUBLIC_SUPABASE_URL e EXPO_PUBLIC_SUPABASE_ANON_KEY. Sem eles o app abre,
// mas entrar falha com a mensagem de "não deu para entrar".
const supabase = createClient(
  process.env.EXPO_PUBLIC_SUPABASE_URL || "http://localhost:54321",
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || "sem-chave",
  {
    auth: {
      storage: AsyncStorage,
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
      flowType: "pkce",
    },
  },
);

definirFonteToken(async () => (await supabase.auth.getSession()).data.session?.access_token ?? null);

// No celular, o token só se renova com o app aberto (recomendação do Supabase para React Native).
if (Platform.OS !== "web") {
  AppState.addEventListener("change", (estadoApp) => {
    if (estadoApp === "active") supabase.auth.startAutoRefresh();
    else supabase.auth.stopAutoRefresh();
  });
}

// No web, fecha a janela do Google ou da Apple quando ela volta para o app.
WebBrowser.maybeCompleteAuthSession();

/** Para onde o Supabase manda de volta depois do Google, da Apple no navegador e do link por e-mail. */
const VOLTA = Linking.createURL("entrar");

// Marca no metadata da conta, e não no aparelho, para valer em qualquer celular.
const MARCA_JA_ENTROU = "ja_entrou";

export type TipoErroEntrar = "provedor" | "link-vencido" | "muitos-pedidos";

const MENSAGENS: Record<TipoErroEntrar, string> = {
  provedor: "Não deu para entrar agora. Tente de novo.",
  "link-vencido": "Esse link venceu. Peça um novo: ele vale por 15 minutos.",
  "muitos-pedidos": "Muitos pedidos seguidos. Espere um minuto e tente de novo.",
};

/** Erro ao entrar; `message` já é o texto para mostrar à pessoa. */
export class ErroEntrar extends Error {
  constructor(readonly tipo: TipoErroEntrar) {
    super(MENSAGENS[tipo]);
    this.name = "ErroEntrar";
  }
}

type EstadoSessao = { sessao: Session | null; carregou: boolean };

let estado: EstadoSessao = { sessao: null, carregou: false };
const ouvintes = new Set<() => void>();

// Dispara já ao abrir (INITIAL_SESSION, lida do aparelho) e a cada entrada, renovação e saída.
supabase.auth.onAuthStateChange((evento, sessao) => {
  estado = { sessao, carregou: true };
  ouvintes.forEach((ouvir) => ouvir());
  if (sessao && (evento === "SIGNED_IN" || evento === "INITIAL_SESSION")) void registrarTokenDePush();
});

/** A sessão atual; `carregou` é false enquanto o aparelho ainda não respondeu. */
export function useSessao(): EstadoSessao {
  return useSyncExternalStore(
    (ouvir) => {
      ouvintes.add(ouvir);
      return () => ouvintes.delete(ouvir);
    },
    () => estado,
  );
}

/** Parâmetros da query e do fragmento (o Supabase manda erros em um ou no outro). */
function parametrosDoLink(url: string): Record<string, string> {
  const parametros: Record<string, string> = {};
  for (const parte of url.split(/[?#]/).slice(1)) {
    new URLSearchParams(parte).forEach((valor, chave) => {
      parametros[chave] = valor;
    });
  }
  return parametros;
}

// O mesmo código pode chegar duas vezes (pelo navegador e pelo deep link); só vale trocar uma.
const trocas = new Map<string, Promise<Session>>();
// Código já trocado (ou recusado) não entra de novo: senão a mesma URL reaberta devolveria a sessão antiga.
const usados = new Set<string>();

async function trocarCodigo(codigo: string): Promise<Session> {
  const { data, error } = await supabase.auth.exchangeCodeForSession(codigo);
  if (error || !data.session) throw new ErroEntrar("provedor");
  return data.session;
}

/**
 * Cria a sessão a partir do link que abriu o app (link por e-mail) ou da volta do navegador.
 *
 * @param url - O link completo, como `desvio://entrar?code=…`.
 * @returns A sessão, ou null se o link não é de login.
 * @throws {@link ErroEntrar} Link vencido ou recusado.
 */
export async function sessaoDoLink(url: string): Promise<Session | null> {
  const parametros = parametrosDoLink(url);
  if (parametros.error_code === "otp_expired") throw new ErroEntrar("link-vencido");
  if (parametros.error || parametros.error_code) throw new ErroEntrar("provedor");
  const codigo = parametros.code;
  if (!codigo || usados.has(codigo)) return null;
  let troca = trocas.get(codigo);
  if (!troca) {
    troca = trocarCodigo(codigo).finally(() => {
      trocas.delete(codigo);
      usados.add(codigo);
    });
    trocas.set(codigo, troca);
  }
  return troca;
}

async function entrarPeloNavegador(provedor: "google" | "apple"): Promise<Session | null> {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: provedor,
    options: { redirectTo: VOLTA, skipBrowserRedirect: true },
  });
  if (error || !data.url) throw new ErroEntrar("provedor");
  const resultado = await WebBrowser.openAuthSessionAsync(data.url, VOLTA);
  if (resultado.type !== "success") return null; // a pessoa fechou o navegador
  return sessaoDoLink(resultado.url);
}

/** Entra com a conta Google. Null quando a pessoa desiste. */
export function entrarComGoogle(): Promise<Session | null> {
  return entrarPeloNavegador("google");
}

/** Entra com a Apple: nativo no iOS (exigência da App Store), pelo navegador no resto. Null quando a pessoa desiste. */
export async function entrarComApple(): Promise<Session | null> {
  if (Platform.OS !== "ios") return entrarPeloNavegador("apple");
  let credencial: AppleAuthentication.AppleAuthenticationCredential;
  try {
    // Só o e-mail: o Desvio não guarda o nome (docs/privacidade.md).
    credencial = await AppleAuthentication.signInAsync({
      requestedScopes: [AppleAuthentication.AppleAuthenticationScope.EMAIL],
    });
  } catch (erro) {
    if ((erro as { code?: string }).code === "ERR_REQUEST_CANCELED") return null;
    throw new ErroEntrar("provedor");
  }
  if (!credencial.identityToken) throw new ErroEntrar("provedor");
  const { data, error } = await supabase.auth.signInWithIdToken({ provider: "apple", token: credencial.identityToken });
  if (error || !data.session) throw new ErroEntrar("provedor");
  return data.session;
}

/**
 * Manda o link de acesso para o e-mail. O link abre o app em /entrar; quanto tempo ele vale
 * (15 min) é configurado no projeto do Supabase.
 *
 * @throws {@link ErroEntrar} Pedidos demais ou falha do Supabase.
 */
export async function pedirLinkPorEmail(email: string): Promise<void> {
  const { error } = await supabase.auth.signInWithOtp({ email: email.trim(), options: { emailRedirectTo: VOLTA } });
  if (!error) return;
  throw new ErroEntrar(error.status === 429 ? "muitos-pedidos" : "provedor");
}

/**
 * Sai da conta neste aparelho. `local` porque, depois de apagar a conta, o token já não vale
 * no Supabase e a saída global falharia; a sessão some do aparelho de qualquer jeito.
 */
export async function sair(): Promise<void> {
  await esquecerTokenDePush();
  await supabase.auth.signOut({ scope: "local" }).catch(() => undefined);
}

/**
 * Para onde ir depois de entrar: o primeiro login da conta vai para a triagem, os seguintes
 * para Minhas viagens. Marca a conta na primeira vez.
 */
export async function destinoDepoisDeEntrar(sessao: Session): Promise<"/triagem" | "/viagens"> {
  if (sessao.user.user_metadata?.[MARCA_JA_ENTROU]) return "/viagens";
  // Se a marca não gravar, a pessoa vê a triagem de novo no próximo login, que ela pode pular.
  await supabase.auth.updateUser({ data: { [MARCA_JA_ENTROU]: true } }).catch(() => undefined);
  return "/triagem";
}
