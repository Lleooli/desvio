/**
 * Fila das decisões do swipe, guardada no aparelho. Cada Bora, Passo, Favorito ou Desfazer
 * entra aqui e é enviada ao coletor na ordem; sem rede, fica guardada e vai quando a rede
 * voltar (nova tentativa a cada 15 s, ao voltar para o app e a cada decisão nova).
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { AppState } from "react-native";
import { decidir, desfazerDecisao, ErroApi, type Card, type TipoDecisao } from "@/api";

const CHAVE = "desvio:fila-decisoes";
const ESPERA_MS = 15_000;

type Pendente =
  // `tentado`: já saiu para o coletor uma vez; um envio que estourou o tempo pode ter gravado.
  | { op: "decidir"; card: Card; tipo: TipoDecisao; viagem: string; parada: number; tentado?: true }
  | { op: "desfazer"; lugarId: string };

let fila: Pendente[] = [];
/** O item que está indo para o coletor agora; ele não pode mais ser cancelado na fila. */
let enviando: Pendente | null = null;
let relogio: ReturnType<typeof setTimeout> | null = null;

// Lê a fila guardada uma vez ao abrir o app; o que entrar antes disso vai depois dela.
const carregada = AsyncStorage.getItem(CHAVE)
  .then((texto) => {
    const guardada: unknown = texto ? JSON.parse(texto) : [];
    if (Array.isArray(guardada)) fila = [...(guardada as Pendente[]), ...fila];
  })
  .catch(() => {});

function guardar(): void {
  // Depois de ler a guardada: gravar antes apagaria o que ficou de outra vez.
  void carregada.then(() => AsyncStorage.setItem(CHAVE, JSON.stringify(fila)).catch(() => {}));
}

function lugarDe(item: Pendente): string {
  return item.op === "decidir" ? item.card.id : item.lugarId;
}

// Pedido recusado (card inválido, decisão que não existe mais) não melhora tentando de novo.
function semJeito(erro: unknown): boolean {
  return erro instanceof ErroApi && (erro.tipo === "pedido" || erro.tipo === "nao-encontrado");
}

async function enviarUm(item: Pendente): Promise<void> {
  if (item.op === "decidir") await decidir(item.card, item.tipo, { viagem: item.viagem, parada: item.parada });
  else await desfazerDecisao(item.lugarId);
}

/** Envia a fila na ordem; para no primeiro erro de rede e tenta de novo depois. */
async function enviar(): Promise<void> {
  await carregada;
  if (enviando) return;
  if (relogio) clearTimeout(relogio);
  relogio = null;
  while (fila.length > 0) {
    const item = fila[0];
    enviando = item;
    if (item.op === "decidir" && !item.tentado) {
      item.tentado = true;
      guardar();
    }
    try {
      await enviarUm(item);
    } catch (erro) {
      if (!semJeito(erro)) {
        enviando = null;
        relogio = setTimeout(() => void enviar(), ESPERA_MS);
        return;
      }
    }
    enviando = null;
    fila = fila.filter((outro) => outro !== item);
    guardar();
  }
}

AppState.addEventListener("change", (estado) => {
  if (estado === "active") void enviar();
});
void enviar(); // o que ficou de outra vez que o app abriu

/**
 * Guarda a decisão sobre um card e manda para o coletor assim que der.
 *
 * @param card - O card como veio de `GET /viagens/{id}`.
 * @param tipo - Bora, Passo ou Favorito.
 * @param onde - A viagem e a ordem da parada.
 */
export function registrarDecisao(card: Card, tipo: TipoDecisao, onde: { viagem: string; parada: number }): void {
  fila.push({ op: "decidir", card, tipo, ...onde });
  guardar();
  void enviar();
}

/**
 * Desfaz a decisão sobre o lugar. Se ela nunca saiu do aparelho, só sai da fila;
 * se já saiu alguma vez (pode ter chegado ao coletor), o desfazer entra na fila.
 */
export function desfazerRegistro(lugarId: string): void {
  const naFila = fila.findLast((item) => lugarDe(item) === lugarId);
  if (naFila?.op === "decidir" && naFila !== enviando) {
    fila = fila.filter((item) => item !== naFila);
    if (naFila.tentado) fila.push({ op: "desfazer", lugarId });
  } else {
    fila.push({ op: "desfazer", lugarId });
  }
  guardar();
  void enviar();
}

/**
 * Joga fora as decisões que ainda não chegaram ao coletor, na memória e no aparelho.
 * Depois de apagar a conta, elas não podem ir para a conta nova de quem entrar.
 */
export async function esvaziarFilaDeDecisoes(): Promise<void> {
  await carregada;
  if (relogio) clearTimeout(relogio);
  relogio = null;
  fila = [];
  await AsyncStorage.removeItem(CHAVE).catch(() => {});
}

/**
 * Os lugares com decisão que ainda não chegou ao coletor. `GET /viagens/{id}` ainda
 * traz esses cards; a tela tira eles da pilha para não aparecerem de novo.
 */
export async function lugaresDecididosNaFila(): Promise<Set<string>> {
  await carregada;
  const decididos = new Set<string>();
  for (const item of fila) {
    if (item.op === "decidir") decididos.add(item.card.id);
    else decididos.delete(item.lugarId);
  }
  return decididos;
}
