import { Redirect, router, useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, AppState, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { criarViagem, mensagemDeErro, obterJob, obterViagem, type EtapaBusca, type Job, type Viagem } from "@/api";
import { useCarregar } from "@/api/useCarregar";
import { Aviso } from "@/componentes/Aviso";
import { Ceu } from "@/componentes/Ceu";
import { Destaque } from "@/componentes/Destaque";
import { Estrada } from "@/componentes/Estrada";
import { Icon } from "@/componentes/Icon";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, useCores } from "@/tema";
import { useMarcarViagemAtiva } from "@/viagemAtiva";

const INTERVALO_CONSULTA_MS = 3_000;

// A ordem das etapas em coletor.planejar_viagem. Rota e cidades chegam quando já terminaram
// ("Rota calculada"); lugares e Instagram chegam quando começam.
const ETAPAS: { etapa: EtapaBusca; rotulo: string; chegaPronta: boolean }[] = [
  { etapa: "rota", rotulo: "Rota", chegaPronta: true },
  { etapa: "cidades", rotulo: "Cidades para parar", chegaPronta: true },
  { etapa: "lugares", rotulo: "Fotos e notas", chegaPronta: false },
  { etapa: "instagram", rotulo: "Instagram dos restaurantes", chegaPronta: false },
];

type EstadoEtapa = "feita" | "andamento" | "pendente";
type Etapa = { etapa: EtapaBusca; estado: EstadoEtapa; titulo: string; detalhe?: string };

/** Cada etapa feita, em andamento ou pendente, com o texto que o coletor mandou para ela. */
function etapasDoJob(job: Job | null, vistas: Partial<Record<EtapaBusca, { titulo: string; detalhe: string }>>): Etapa[] {
  const atual = job?.progresso ? ETAPAS.findIndex((e) => e.etapa === job.progresso?.etapa) : -1;
  // Sem progresso, a rota está sendo calculada; etapa que chega pronta passa a vez à seguinte.
  const emAndamento = atual < 0 ? 0 : ETAPAS[atual].chegaPronta ? atual + 1 : atual;
  return ETAPAS.map(({ etapa, rotulo }, i) => {
    const estado: EstadoEtapa = job?.status === "pronto" || i < emAndamento ? "feita" : i === emAndamento ? "andamento" : "pendente";
    const vista = vistas[etapa];
    return { etapa, estado, titulo: vista?.titulo ?? rotulo, detalhe: vista?.detalhe };
  });
}

/** "Alegrete, RS" vira "Alegrete". */
const semUf = (rotulo: string) => rotulo.split(",")[0].trim();

type Acompanhamento = { job: Job | null; erro: string | null; tentarDeNovo: () => void };

/**
 * Consulta GET /jobs/{id} a cada 3 s enquanto a tela está aberta e o app em primeiro plano;
 * volta do segundo plano consultando na hora. Para quando o job termina ou falha.
 */
function useAcompanharBusca(jobId: string | null): Acompanhamento {
  const [job, setJob] = useState<Job | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const [focada, setFocada] = useState(false);
  const [ativo, setAtivo] = useState(AppState.currentState === "active");

  useFocusEffect(
    useCallback(() => {
      setFocada(true);
      return () => setFocada(false);
    }, []),
  );

  useEffect(() => {
    const assinatura = AppState.addEventListener("change", (estado) => setAtivo(estado === "active"));
    return () => assinatura.remove();
  }, []);

  const terminou = job?.status === "pronto" || job?.status === "falhou";

  useEffect(() => {
    if (!jobId || !focada || !ativo || terminou || erro) return;
    let valendo = true;
    let relogio: ReturnType<typeof setTimeout> | undefined;
    const consultar = () =>
      obterJob(jobId).then(
        (novo) => {
          if (!valendo) return;
          setJob(novo);
          if (novo.status !== "pronto" && novo.status !== "falhou") relogio = setTimeout(consultar, INTERVALO_CONSULTA_MS);
        },
        (e: unknown) => valendo && setErro(mensagemDeErro(e)),
      );
    consultar();
    return () => {
      valendo = false;
      clearTimeout(relogio);
    };
  }, [jobId, focada, ativo, terminou, erro, tentativa]);

  const tentarDeNovo = useCallback(() => {
    setErro(null);
    setTentativa((t) => t + 1);
  }, []);
  return { job, erro, tentarDeNovo };
}

/** A busca falhou: começa outra igual, numa viagem nova, e acompanha essa. */
async function buscarDeNovo(viagem: Viagem): Promise<void> {
  const nova = await criarViagem({
    origem: viagem.origem,
    destino: viagem.destino,
    veiculo: viagem.veiculo,
    intervalo_km: viagem.intervalo_km,
    categorias: viagem.categorias,
  });
  router.replace({ pathname: "/viagens/[id]/carregando", params: { id: nova.viagem_id } });
}

function Acompanhar({ viagem }: { viagem: Viagem }) {
  const { c } = useCores();
  const margens = useSafeAreaInsets();
  const { job, erro, tentarDeNovo } = useAcompanharBusca(viagem.job_id);
  const vistas = useRef<Partial<Record<EtapaBusca, { titulo: string; detalhe: string }>>>({});
  const [erroNovaBusca, setErroNovaBusca] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  if (job?.progresso) vistas.current[job.progresso.etapa] = { titulo: job.progresso.titulo, detalhe: job.progresso.detalhe };

  useEffect(() => {
    if (job?.status === "pronto") router.replace({ pathname: "/viagens/[id]/paradas", params: { id: viagem.id } });
  }, [job?.status, viagem.id]);

  if (erro) return <Aviso mensagem={erro} acao="Tentar de novo" onAcao={tentarDeNovo} />;
  if (!viagem.job_id || job?.status === "falhou") {
    const novaBusca = () => {
      setOcupado(true);
      setErroNovaBusca(null);
      buscarDeNovo(viagem).catch((e: unknown) => {
        setErroNovaBusca(mensagemDeErro(e));
        setOcupado(false);
      });
    };
    const mensagem = erroNovaBusca ?? job?.erro ?? "Não deu para buscar as paradas dessa viagem.";
    return <Aviso mensagem={mensagem} acao={ocupado ? "Buscando…" : "Tentar de novo"} onAcao={ocupado ? () => {} : novaBusca} />;
  }

  const paradas = (job?.resultado ?? job?.parcial)?.paradas;
  const cidades = [semUf(viagem.origem), ...(paradas?.map((p) => p.nome) ?? [semUf(viagem.destino)])];
  const percentual = job?.status === "pronto" ? 100 : (job?.progresso?.percentual ?? 0);

  return (
    <View style={[s.tela, { backgroundColor: c["surface-100"], paddingBottom: margens.bottom + espaco["space-6"] }]}>
      <Ceu variante="placa" serra>
        <View style={{ paddingTop: margens.top }}>
          <Text style={[estiloTexto("label"), s.trajeto, { color: c["ink-muted"] }]}>
            {semUf(viagem.origem)} → {semUf(viagem.destino)}
          </Text>
          <View style={s.estrada}>
            <Estrada cidades={cidades} variante="curva" />
          </View>
          <Text accessibilityRole="header" style={[estiloTexto("display-xl"), { color: c.ink }]}>
            Procurando <Destaque>paradas</Destaque> no caminho
          </Text>
        </View>
      </Ceu>

      <View style={s.corpo}>
        <View
          accessibilityRole="progressbar"
          accessibilityLabel="Progresso da busca"
          accessibilityValue={{ min: 0, max: 100, now: percentual }}
          style={[s.barra, { backgroundColor: c["surface-300"] }]}
        >
          <View style={[s.preenchido, { width: `${percentual}%`, backgroundColor: c.asfalto }]} />
        </View>
        <View style={s.etapas}>
          {etapasDoJob(job, vistas.current).map((etapa) => (
            <ItemEtapa key={etapa.etapa} {...etapa} />
          ))}
        </View>
      </View>

      <Text style={[estiloTexto("body-s"), s.aviso, { color: c["ink-muted"] }]}>
        Pode fechar o app. A busca continua, e a viagem fica em Minhas viagens.
      </Text>
    </View>
  );
}

function ItemEtapa({ estado, titulo, detalhe }: Etapa) {
  const { c } = useCores();
  const marca =
    estado === "feita" ? (
      <View style={[s.marca, { backgroundColor: c.placa }]}>
        <Icon name="check" size={tamanhoIcone.chip} color={c["on-placa"]} label="Feito" />
      </View>
    ) : estado === "andamento" ? (
      <View style={[s.marca, { backgroundColor: c.faixa }]}>
        <Icon name="clock" size={tamanhoIcone.chip} color={c["on-faixa"]} label="Em andamento" />
      </View>
    ) : (
      <View style={[s.marca, s.pendente, { borderColor: c["ink-muted"] }]} accessibilityLabel="Pendente" />
    );
  const cor = estado === "pendente" ? c["ink-muted"] : c.ink;
  return (
    <View style={s.etapa}>
      {marca}
      <View style={s.textoEtapa}>
        <Text style={[estiloTexto("body-strong"), { color: cor }]}>{titulo}</Text>
        {detalhe && estado !== "pendente" ? (
          <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>{detalhe}</Text>
        ) : null}
      </View>
    </View>
  );
}

/** As etapas da busca (HU07): consulta o job a cada 3 s e, quando fica pronto, vai para as paradas. */
export default function Carregando() {
  const { id } = useLocalSearchParams<{ id: string }>();
  useMarcarViagemAtiva(id);
  const { c } = useCores();
  const { dados: viagem, erro, carregando, tentarDeNovo } = useCarregar(id ?? null, obterViagem);

  if (erro) return <Aviso mensagem={erro} acao="Tentar de novo" onAcao={tentarDeNovo} />;
  if (!viagem || carregando) {
    return (
      <View style={[s.centro, { backgroundColor: c["surface-100"] }]}>
        <ActivityIndicator color={c.placa} accessibilityLabel="Carregando a viagem" />
      </View>
    );
  }
  // Reaberta depois de pronta, a viagem vai direto para as paradas.
  if (viagem.status === "pronta") return <Redirect href={{ pathname: "/viagens/[id]/paradas", params: { id: viagem.id } }} />;
  return <Acompanhar viagem={viagem} />;
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  centro: { flex: 1, justifyContent: "center", alignItems: "center" },
  trajeto: { marginTop: espaco["space-4"], textTransform: "uppercase" },
  estrada: { marginTop: espaco["space-6"], marginBottom: espaco["space-2"], marginHorizontal: -espaco["space-4"] },
  corpo: { gap: espaco["space-4"], paddingTop: espaco["space-1"], paddingHorizontal: espaco["space-4"] },
  barra: { height: medida.barraBusca, borderRadius: raio["radius-pill"], overflow: "hidden" },
  preenchido: { height: "100%", borderRadius: raio["radius-pill"] },
  etapas: { gap: espaco["space-3"] },
  etapa: { flexDirection: "row", gap: espaco["space-3"], alignItems: "flex-start" },
  marca: {
    width: medida.marcaEtapa,
    height: medida.marcaEtapa,
    borderRadius: raio["radius-pill"],
    alignItems: "center",
    justifyContent: "center",
  },
  pendente: { borderWidth: medida.foco },
  textoEtapa: { flex: 1 },
  aviso: { marginTop: "auto", textAlign: "center", paddingHorizontal: espaco["space-4"] },
});
