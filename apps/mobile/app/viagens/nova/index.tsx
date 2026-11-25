import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { buscarCidades, criarViagem, mensagemDeErro, type Cidade, type Veiculo } from "@/api";
import { Button } from "@/componentes/Button";
import { Ceu } from "@/componentes/Ceu";
import { categorias, Chip, type Categoria } from "@/componentes/Chip";
import { Destaque } from "@/componentes/Destaque";
import { Icon } from "@/componentes/Icon";
import { Segmented } from "@/componentes/Segmented";
import { TextField } from "@/componentes/TextField";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, useCores } from "@/tema";

// Só por terra (PRD, HU06): carro, moto ou bicicleta.
const MODOS: { valor: Veiculo; label: string; icon: "car" | "moto" | "bike" }[] = [
  { valor: "carro", label: "Carro", icon: "car" },
  { valor: "moto", label: "Moto", icon: "moto" },
  { valor: "bicicleta", label: "Bicicleta", icon: "bike" },
];
const INTERVALOS = [150, 200, 300].map((km) => ({ valor: km, label: `${km} km` }));
// O perfil ainda não guarda um intervalo próprio; quando guardar, ele entra aqui no lugar do 200.
const INTERVALO_PADRAO = 200;
const CATEGORIAS_PADRAO: Categoria[] = ["turismo", "restaurante", "posto"];

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

/** Nova viagem por terra (canvas NovaViagem): origem, destino, intervalo e categorias, e daí a busca. */
export default function NovaViagem() {
  const { c } = useCores();
  const router = useRouter();
  const margens = useSafeAreaInsets();
  const [modo, setModo] = useState<Veiculo>("carro");
  const [origem, setOrigem] = useState<Campo>({ texto: "" });
  const [destino, setDestino] = useState<Campo>({ texto: "" });
  const [intervalo, setIntervalo] = useState(INTERVALO_PADRAO);
  const [escolhidas, setEscolhidas] = useState<Categoria[]>(CATEGORIAS_PADRAO);
  const [avisoCategoria, setAvisoCategoria] = useState(false);
  const [erro, setErro] = useState<string>();
  const [ocupado, setOcupado] = useState(false);

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

  return (
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
        <View style={s.secao}>
          <Text style={rotuloSecao}>Parar a cada</Text>
          <Segmented block rotulo="Distância entre paradas" opcoes={INTERVALOS} valor={intervalo} onChange={setIntervalo} />
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
  );
}

const s = StyleSheet.create({
  tela: { flexGrow: 1 },
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
