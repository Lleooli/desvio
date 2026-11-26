/**
 * Erros do app no Sentry (issue #42). Sem EXPO_PUBLIC_SENTRY_DSN, nada é ligado
 * e o app abre do mesmo jeito. O evento não leva e-mail, nome, token nem coordenada.
 */
import Constants from "expo-constants";
import * as Sentry from "@sentry/react-native";

const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
const BEARER = /Bearer\s+\S+/gi;
const CHAVES = new Set([
  "authorization", "cookie", "cookies", "set-cookie", "x-admin-token",
  "email", "e-mail", "username", "ip_address", "nome",
  "origem", "destino", "endereco",
  "token", "access_token", "refresh_token", "password", "senha",
  "lat", "lon", "latitude", "longitude",
]);

function limparTexto(valor: string): string {
  return valor.replace(EMAIL, "[e-mail]").replace(BEARER, "Bearer [token]");
}

/** Tira dado pessoal de qualquer ramo do evento antes do envio. */
export function limparEvento(valor: unknown): unknown {
  if (typeof valor === "string") return limparTexto(valor);
  if (Array.isArray(valor)) return valor.map(limparEvento);
  if (valor && typeof valor === "object") {
    const saida: Record<string, unknown> = {};
    for (const [chave, item] of Object.entries(valor)) {
      if (CHAVES.has(chave.toLowerCase())) continue;
      saida[chave] = limparEvento(item);
    }
    return saida;
  }
  return valor;
}

/** Liga o Sentry só quando o DSN existe. release segue a versão do app.json. */
export function iniciarObservabilidade(): void {
  const dsn = process.env.EXPO_PUBLIC_SENTRY_DSN?.trim();
  if (!dsn) return;
  const versao = Constants.expoConfig?.version ?? "0.1.0";
  Sentry.init({
    dsn,
    environment: process.env.EXPO_PUBLIC_SENTRY_ENVIRONMENT || "desenvolvimento",
    release: `desvio@${versao}`,
    sendDefaultPii: false,
    beforeSend(evento) {
      const limpo = limparEvento(evento) as typeof evento;
      if (limpo && typeof limpo === "object") delete limpo.user;
      return limpo;
    },
  });
}
