import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Keyboard, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { buscarCidades, criarViagem, mensagemDeErro, obterPerfilGosto, type Cidade, type Veiculo } from "@/api";
import { Button } from "@/componentes/Button";
import { Ceu } from "@/componentes/Ceu";
import { categorias, Chip, type Categoria } from "@/componentes/Chip";
import { Destaque } from "@/componentes/Destaque";
import { FaixaDoStatus } from "@/componentes/FaixaDoStatus";
import { Icon } from "@/componentes/Icon";
import { Segmented } from "@/componentes/Segmented";
import { TextField } from "@/componentes/TextField";
import { INTERVALO_PADRAO, INTERVALOS } from "@/intervalos";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, useCores } from "@/tema";

// Só por terra (PRD, HU06): carro, moto ou bicicleta.
const MODOS: { valor: Veiculo; label: string; icon: "car" | "moto" | "bike" }[] = [
  { valor: "carro", label: "Carro", icon: "car" },
  { valor: "moto", label: "Moto", icon: "moto" },
  { valor: "bicicleta", label: "Bicicleta", icon: "bike" },
];
const CATEGORIAS_PADRAO: Categoria[] = ["turismo", "restaurante", "posto"];
// Hora de saída: começa às 7h e anda de 30 em 30 minutos (a mesma do Roteiro).
const SAIDA_PADRAO = 7 * 60;
const PASSO_SAIDA = 30;
const MINUTOS_NO_DIA = 24 * 60;
const DATA_INVALIDA = "Use o formato DD/MM/AAAA, com uma data que existe.";

/** "7h", "13h30": a hora no formato brasileiro. */
function hora(minutos: number): string {
  const h = Math.floor(minutos / 60);
  const m = minutos % 60;
  return m ? `${h}h${String(m).padStart(2, "0")}` : `${h}h`;
}

/** "07:00": a hora no formato que o coletor recebe. */
function horaHHMM(minutos: number): string {
  return `${String(Math.floor(minutos / 60)).padStart(2, "0")}:${String(minutos % 60).padStart(2, "0")}`;
}

/**
 * A data que a pessoa digitou (DD/MM/AAAA) no formato do coletor (AAAA-MM-DD).
 *
 * @returns undefined com o campo vazio; null quando não é uma data que existe.
 */
function dataDaSaida(texto: string): string | null | undefined {
  const limpo = texto.trim();
  if (!limpo) return undefined;
  const partes = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(limpo);
  if (!partes) return null;
  const [dia, mes, ano] = [Number(partes[1]), Number(partes[2]), Number(partes[3])];
  const data = new Date(Date.UTC(ano, mes - 1, dia));
  if (data.getUTCFullYear() !== ano || data.getUTCMonth() !== mes - 1 || data.getUTCDate() !== dia) return null;
  return `${ano}-${String(mes).padStart(2, "0")}-${String(dia).padStart(2, "0")}`;
}

// O mesmo mínimo de GET /cidades (cidades.MINIMO_LETRAS no coletor).
const MINIMO_LETRAS = 3;
const ESPERA_DIGITACAO_MS = 300;
const CIDADE_INEXISTENTE = "Não achamos essa cidade. Confira a grafia.";

/** "Vitória da Conquista , ba" e "vitoria da conquista, BA" viram a mesma chave. */
function chave(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ") // como o normalizar do coletor (app/cidades.py)
    .trim();
}

/** O rótulo "Cidade, UF" do município que o texto nomeia, ou null se nenhum bate. */
async function confirmarCidade(texto: string): Promise<string | null> {
  if (chave(texto).length < MINIMO_LETRAS) return null;
  const achadas = await buscarCidades(texto.trim());
  return achadas.find((c) => chave(c.rotulo) === chave(texto))?.rotulo ?? null;
}

type Campo = { texto: string; erro?: string };

/** Origem ou destino, com as sugestões de GET /cidades enquanto a pessoa digita. */
function CampoCidade({ label, campo, onChange }: { label: string; campo: Campo; onChange: (campo: Campo) => void }) {
  const { c } = useCores();
  const [sugestoes, setSugestoes] = useState<Cidade[]>([]);
  const [focado, setFocado] = useState(false);

  useEffect(() => {
    const texto = campo.texto.trim();
    if (!focado || chave(texto).length < MINIMO_LETRAS) {
      setSugestoes([]);
      return;
    }
    let valendo = true; // resposta de um texto antigo não sobrescreve a do atual
    const relogio = setTimeout(() => {
      buscarCidades(texto).then(
        (achadas) => valendo && setSugestoes(achadas.some((a) => chave(a.rotulo) === chave(texto)) ? [] : achadas),
        () => valendo && setSugestoes([]), // sem sugestão; o erro aparece ao buscar paradas
      );
    }, ESPERA_DIGITACAO_MS);
    return () => {
      valendo = false;
      clearTimeout(relogio);
    };
  }, [campo.texto, focado]);

  return (
    <View style={s.campoCidade}>
      <TextField
        label={label}
        icon="pin"
        placeholder="Cidade, UF"
        value={campo.texto}
        onChangeText={(texto) => onChange({ texto })}
        onFocus={() => setFocado(true)}
        onBlur={() => setFocado(false)}
        autoCorrect={false}
        autoCapitalize="words"
        erro={campo.erro}
      />
      {sugestoes.length > 0 ? (
        <View style={[s.sugestoes, { backgroundColor: c["surface-200"], borderColor: c.line }]}>
          {sugestoes.map((cidade) => (
            <Pressable
              key={cidade.codigo_ibge}
              onPress={() => {
                onChange({ texto: cidade.rotulo });
                setSugestoes([]);
                Keyboard.dismiss(); // cidade escolhida: o teclado não fica cobrindo o resto do formulário
              }}
              accessibilityRole="button"
              accessibilityLabel={cidade.rotulo}
              style={({ pressed }) => [s.sugestao, pressed && { backgroundColor: c["surface-300"] }]}
            >
              <Text style={[estiloTexto("body"), { color: c.ink }]}>{cidade.rotulo}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

/**
 * Nova viagem por terra (canvas NovaViagem): origem, destino, hora de saída, data opcional,
 * intervalo e categorias, e daí a busca. A saída decide onde cada dia acaba e em que
 * cidades a busca procura onde dormir.
 */
export default function NovaViagem() {
  const { c } = useCores();
  const router = useRouter();
  const margens = useSafeAreaInsets();
  const [modo, setModo] = useState<Veiculo>("carro");
  const [origem, setOrigem] = useState<Campo>({ texto: "" });
  const [destino, setDestino] = useState<Campo>({ texto: "" });
  const [intervalo, setIntervalo] = useState(INTERVALO_PADRAO);
  const [mexeuNoIntervalo, setMexeuNoIntervalo] = useState(false);
  const [escolhidas, setEscolhidas] = useState<Categoria[]>(CATEGORIAS_PADRAO);
  const [avisoCategoria, setAvisoCategoria] = useState(false);
  const [saida, setSaida] = useState(SAIDA_PADRAO);
  const [data, setData] = useState<Campo>({ texto: "" });
  const [erro, setErro] = useState<string>();
  const [ocupado, setOcupado] = useState(false);

  // O intervalo padrão do perfil; se não carregar, fica o do app. Não desfaz a escolha da pessoa.
  useEffect(() => {
    if (mexeuNoIntervalo) return;
    let valendo = true;
    obterPerfilGosto().then(
      (perfil) => valendo && perfil.intervalo_km !== null && setIntervalo(perfil.intervalo_km),
      () => {},
    );
    return () => {
      valendo = false;
    };
  }, [mexeuNoIntervalo]);

  function escolherIntervalo(km: number) {
    setMexeuNoIntervalo(true);
    setIntervalo(km);
  }

  function alternar(categoria: Categoria) {
    const ligada = escolhidas.includes(categoria);
    if (ligada && escolhidas.length === 1) {
      setAvisoCategoria(true); // a última fica ligada: sem categoria não há o que buscar
      return;
    }
    setAvisoCategoria(false);
    setEscolhidas(ligada ? escolhidas.filter((x) => x !== categoria) : [...escolhidas, categoria]);
  }

  async function buscarParadas() {
    setErro(undefined);
    const dataIso = dataDaSaida(data.texto);
    if (dataIso === null) {
      setData({ texto: data.texto, erro: DATA_INVALIDA });
      return;
    }
    setOcupado(true);
    try {
      const [rotuloOrigem, rotuloDestino] = await Promise.all([
        confirmarCidade(origem.texto),
        confirmarCidade(destino.texto),
      ]);
      if (!rotuloOrigem || !rotuloDestino) {
        setOrigem({ texto: origem.texto, erro: rotuloOrigem ? undefined : CIDADE_INEXISTENTE });
        setDestino({ texto: destino.texto, erro: rotuloDestino ? undefined : CIDADE_INEXISTENTE });
        return;
      }
      const criada = await criarViagem({
        origem: rotuloOrigem,
        destino: rotuloDestino,
        veiculo: modo,
        intervalo_km: intervalo,
        categorias: escolhidas,
        saida: horaHHMM(saida),
        ...(dataIso ? { data: dataIso } : {}),
      });
      router.replace({ pathname: "/viagens/[id]/carregando", params: { id: criada.viagem_id } });
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }

  function fechar() {
    if (router.canGoBack()) router.back();
    else router.replace("/viagens");
  }

  const rotuloSecao = [estiloTexto("body-strong"), { color: c.ink }];
  const mudarSaida = (delta: number) => setSaida((atual) => (atual + delta + MINUTOS_NO_DIA) % MINUTOS_NO_DIA);

  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        style={{ backgroundColor: c["surface-100"] }}
        contentContainerStyle={[s.tela, { paddingBottom: margens.bottom + espaco["space-6"] }]}
        keyboardShouldPersistTaps="handled"
      >
        <Ceu serra>
          <View style={{ paddingTop: margens.top }}>
            <Pressable onPress={fechar} accessibilityRole="button" accessibilityLabel="Voltar para suas viagens" style={s.fechar}>
              <Icon name="x" size={tamanhoIcone.nav} color={c.ink} />
            </Pressable>
            <Text accessibilityRole="header" style={[estiloTexto("display-xl"), { color: c.ink }]}>
              Para onde a <Destaque>estrada</Destaque> te leva?
            </Text>
          </View>
        </Ceu>

        <View style={s.formulario}>
          <Segmented block rotulo="Como você vai?" opcoes={MODOS} valor={modo} onChange={setModo} />

          <CampoCidade label="De onde você sai?" campo={origem} onChange={setOrigem} />
          <CampoCidade label="Para onde vai?" campo={destino} onChange={setDestino} />
          <View style={s.saida}>
            <Text style={rotuloSecao}>Hora de saída</Text>
            <View style={s.seletor}>
              <BotaoHora rotulo="−" leitura="30 minutos mais cedo" onPress={() => mudarSaida(-PASSO_SAIDA)} />
              <Text
                accessibilityLabel={`Saída às ${hora(saida)}`}
                accessibilityLiveRegion="polite"
                style={[estiloTexto("km"), s.horaSaida, { color: c.ink }]}
              >
                {hora(saida)}
              </Text>
              <BotaoHora rotulo="+" leitura="30 minutos mais tarde" onPress={() => mudarSaida(PASSO_SAIDA)} />
            </View>
          </View>
          <TextField
            label="Quando você sai?"
            icon="clock"
            placeholder="DD/MM/AAAA"
            hint="Opcional. Com a data, o roteiro confere se os lugares abrem nesse dia."
            value={data.texto}
            onChangeText={(texto) => setData({ texto })}
            keyboardType="numbers-and-punctuation"
            maxLength={10}
            erro={data.erro}
          />
          <View style={s.secao}>
            <Text style={rotuloSecao}>Parar a cada</Text>
            <Segmented block rotulo="Distância entre paradas" opcoes={INTERVALOS} valor={intervalo} onChange={escolherIntervalo} />
          </View>
          <View style={s.secao}>
            <Text style={rotuloSecao}>O que procurar no caminho</Text>
            <View style={s.chips}>
              {(Object.keys(categorias) as Categoria[]).map((categoria) => (
                <Chip
                  key={categoria}
                  categoria={categoria}
                  selected={escolhidas.includes(categoria)}
                  onPress={() => alternar(categoria)}
                />
              ))}
            </View>
            {avisoCategoria ? (
              <Text accessibilityRole="alert" style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>
                Deixe pelo menos uma categoria ligada.
              </Text>
            ) : null}
          </View>
        </View>

        <View style={s.rodape}>
          {erro ? (
            <Text accessibilityRole="alert" style={[estiloTexto("body-s"), s.centro, { color: c.perigo }]}>
              {erro}
            </Text>
          ) : null}
          <Button block disabled={ocupado} onPress={buscarParadas}>
            Buscar paradas
          </Button>
        </View>
      </ScrollView>
      <FaixaDoStatus cor="ceu-base" />
    </View>
  );
}

/** Botão redondo de − e + da hora de saída. */
function BotaoHora({ rotulo, leitura, onPress }: { rotulo: string; leitura: string; onPress: () => void }) {
  const { c } = useCores();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={leitura}
      style={({ pressed }) => [s.botaoHora, { backgroundColor: pressed ? c["surface-300"] : c["surface-200"] }]}
    >
      <Text style={[estiloTexto("title"), { color: c.ink }]}>{rotulo}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  tela: { flexGrow: 1 },
  saida: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  seletor: { flexDirection: "row", alignItems: "center", gap: espaco["space-3"] },
  horaSaida: { minWidth: espaco.touch, textAlign: "center" },
  botaoHora: {
    width: espaco.touch,
    height: espaco.touch,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: raio["radius-pill"],
  },
  fechar: {
    width: espaco.touch,
    height: espaco.touch,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: -espaco["space-3"],
    marginBottom: espaco["space-3"],
  },
  formulario: { gap: espaco["space-4"], paddingTop: espaco["space-1"], paddingHorizontal: espaco["space-4"] },
  campoCidade: { gap: espaco["space-1"] },
  sugestoes: { borderWidth: medida.borda, borderRadius: raio["radius-md"], overflow: "hidden" },
  sugestao: { minHeight: espaco.touch, justifyContent: "center", paddingHorizontal: espaco["space-4"] },
  secao: { gap: espaco["space-2"] },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: espaco["space-2"] },
  rodape: { marginTop: "auto", gap: espaco["space-3"], paddingTop: espaco["space-6"], paddingHorizontal: espaco["space-4"] },
  centro: { textAlign: "center" },
});
