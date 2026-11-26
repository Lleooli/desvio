/**
 * Aviso quando a busca termina (HU07). Sem permissão, no simulador ou no Expo Go,
 * nada disso aparece para a pessoa: a busca segue do mesmo jeito.
 */
import Constants, { ExecutionEnvironment } from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { router } from "expo-router";
import { Platform } from "react-native";
import { chamar } from "@/api/cliente";

const CANAL = "busca";
const jaTratados = new Set<string>();
let ouvindo = false;

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

function viagemDoAviso(dados: unknown): string | null {
  if (!dados || typeof dados !== "object") return null;
  const id = (dados as { viagem_id?: unknown }).viagem_id;
  return typeof id === "string" && id.length > 0 ? id : null;
}

/** Abre as paradas da viagem que o aviso trouxe. Sem viagem no payload, não navega. */
export function abrirParadasDoAviso(dados: unknown): void {
  const viagem = viagemDoAviso(dados);
  if (!viagem) return;
  router.push({ pathname: "/viagens/[id]/paradas", params: { id: viagem } });
}

function tratarToque(resposta: Notifications.NotificationResponse | null): void {
  if (!resposta) return;
  const chave = resposta.notification.request.identifier;
  if (jaTratados.has(chave)) return;
  jaTratados.add(chave);
  // Sem limpar, o mesmo toque volta em toda abertura a frio e reabre uma viagem antiga.
  void Notifications.clearLastNotificationResponseAsync().catch(() => undefined);
  abrirParadasDoAviso(resposta.notification.request.content.data);
}

/** Toque no aviso com o app aberto, em segundo plano ou fechado. */
export function ouvirToqueNoPush(): void {
  if (ouvindo) return;
  ouvindo = true;
  Notifications.addNotificationResponseReceivedListener(tratarToque);
  void Notifications.getLastNotificationResponseAsync().then(tratarToque).catch(() => undefined);
}

/** Pede permissão e manda o token para a API. Recusa ou falta de suporte some em silêncio. */
export async function registrarTokenDePush(): Promise<void> {
  try {
    if (Platform.OS === "web" || !Device.isDevice) return;
    if (Constants.executionEnvironment === ExecutionEnvironment.StoreClient) return;
    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync(CANAL, {
        name: "Busca",
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }
    const atual = await Notifications.getPermissionsAsync();
    const status = atual.status === "granted" ? atual.status : (await Notifications.requestPermissionsAsync()).status;
    if (status !== "granted") return;
    const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
    if (!projectId) return;
    const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
    await chamar("/eu/push-token", { metodo: "POST", corpo: { token } });
  } catch {
    // permissão negada, simulador ou Expo Go: a pessoa segue sem o aviso
  }
}

/** Tira o token deste aparelho ao sair, para o aviso não chegar na conta de outra pessoa. */
export async function esquecerTokenDePush(): Promise<void> {
  try {
    await chamar("/eu/push-token", { metodo: "POST", corpo: { token: null } });
  } catch {
    // sair da conta não depende do aviso
  }
}
