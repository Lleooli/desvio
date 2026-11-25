import { Link, router, useFocusEffect } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useCallback, useEffect, useRef, useState } from "react";
import { ScrollView, Share, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  ajustarPerfil,
  apagarMinhaConta,
  exportarMeusDados,
  mensagemDeErro,
  obterPerfilGosto,
  type AjustePerfil,
  type EscolhaTema,
  type PerfilGosto,
} from "@/api";
import { useCarregar } from "@/api/useCarregar";
import { Aviso } from "@/componentes/Aviso";
import { Button } from "@/componentes/Button";
import { categorias, type Categoria } from "@/componentes/Chip";
import { Destaque } from "@/componentes/Destaque";
import { FolhaApagarConta } from "@/componentes/FolhaApagarConta";
import { Icon } from "@/componentes/Icon";
import { Segmented } from "@/componentes/Segmented";
import { TextField } from "@/componentes/TextField";
import { esvaziarFilaDeDecisoes } from "@/filaDecisoes";
import { INTERVALO_PADRAO, INTERVALOS } from "@/intervalos";
import { sair } from "@/sessao";
import { definirTema, espaco, estiloTexto, medida, raio, tamanhoIcone, useCores, useEscolhaTema } from "@/tema";
import { esquecerViagemAtiva } from "@/viagemAtiva";

/** HU16: a taxa por categoria só aparece a partir de tantas decisões. */
const MINIMO_DECISOES = 20;

/** A política de privacidade (docs/privacidade.md); o .env pode apontar para a versão publicada. */
const LINK_PRIVACIDADE =
  process.env.EXPO_PUBLIC_PRIVACIDADE_URL || "https://github.com/Lleooli/desvio/blob/main/docs/privacidade.md";

/**
 * HU19 (LGPD): exportar os dados em JSON pela folha de compartilhar do sistema, apagar a conta
 * com confirmação e ler a política de privacidade.
 */
function SeusDados() {
  const { c } = useCores();
  const [exportando, setExportando] = useState(false);
  const [erroExportar, setErroExportar] = useState<string>();
  const [folhaAberta, setFolhaAberta] = useState(false);
  const [apagando, setApagando] = useState(false);
  const [erroApagar, setErroApagar] = useState<string>();

  async function exportar() {
    setExportando(true);
    setErroExportar(undefined);
    try {
      const dados = await exportarMeusDados();
      await Share.share({ title: "Seus dados do Desvio", message: JSON.stringify(dados, null, 2) });
    } catch (e) {
      setErroExportar(mensagemDeErro(e));
    } finally {
      setExportando(false);
    }
  }

  async function apagar() {
    setApagando(true);
    setErroApagar(undefined);
    try {
      await apagarMinhaConta();
    } catch (e) {
      setErroApagar(mensagemDeErro(e));
      setApagando(false);
      return;
    }
    // Os dados já sumiram no servidor; o que ficou no aparelho também sai, e a sessão junto.
    await esvaziarFilaDeDecisoes();
    esquecerViagemAtiva();
    await sair();
    setFolhaAberta(false);
    router.replace("/boas-vindas");
  }

  function abrirFolha() {
    setErroApagar(undefined);
    setFolhaAberta(true);
  }

  return (
    <View style={s.secao}>
      <Text accessibilityRole="header" style={[estiloTexto("title"), { color: c.ink }]}>
        Seus dados
      </Text>
      <Text style={[estiloTexto("body"), { color: c["ink-muted"] }]}>
        Guardamos seu e-mail, suas viagens, suas decisões e o perfil de gosto. Você pode levar uma cópia ou apagar tudo.
      </Text>
      <View style={s.botoes}>
        <Button size="sm" variant="secondary" disabled={exportando} onPress={exportar}>
          {exportando ? "Exportando..." : "Exportar meus dados"}
        </Button>
        <Button size="sm" variant="secondary" disabled={apagando} onPress={abrirFolha}>
          Apagar conta
        </Button>
      </View>
      {erroExportar ? (
        <Text accessibilityRole="alert" style={[estiloTexto("body-s"), { color: c.perigo }]}>
          {erroExportar}
        </Text>
      ) : null}
      <Text
        accessibilityRole="link"
        style={[estiloTexto("body-strong"), s.link, { color: c.placa }]}
        onPress={() => WebBrowser.openBrowserAsync(LINK_PRIVACIDADE)}
      >
        Política de privacidade
      </Text>
      <FolhaApagarConta
        visivel={folhaAberta}
        apagando={apagando}
        erro={erroApagar}
        onApagar={apagar}
        onFechar={() => setFolhaAberta(false)}
      />
    </View>
  );
}

const TEMAS: { valor: EscolhaTema; label: string }[] = [
  { valor: "claro", label: "Claro" },
  { valor: "escuro", label: "Escuro" },
  { valor: "sistema", label: "Sistema" },
];

function ehCategoria(nome: string): nome is Categoria {
  return nome in categorias;
}

/** "1 lugar", "148 lugares", "1.204 lugares". */
function lugares(n: number): string {
  return `${n.toLocaleString("pt-BR")} ${n === 1 ? "lugar" : "lugares"}`;
}

/** As taxas de aceite por categoria, da maior para a menor (canvas Perfil). */
function GostoAprendido({ perfil }: { perfil: PerfilGosto }) {
  const { c } = useCores();
  const linhas = Object.entries(perfil.categoria)
    .filter(([nome]) => ehCategoria(nome))
    .sort(([, a], [, b]) => b.taxa - a.taxa);
  if (linhas.length === 0) return null;
  return (
    <View style={[s.gosto, { backgroundColor: c["surface-200"] }]}>
      {linhas.map(([nome, { taxa }]) => {
        const { label, icon } = categorias[nome as Categoria];
        const porcentagem: `${number}%` = `${Math.round(taxa * 100)}%`;
        return (
          <View key={nome} style={s.linhaGosto} accessible accessibilityLabel={`${label}: você aceita ${porcentagem}`}>
            <View style={s.rotuloGosto}>
              <Icon name={icon} size={tamanhoIcone.botaoSm} color={c.ink} />
              <Text style={[estiloTexto("body-strong"), { color: c.ink }]}>{label}</Text>
            </View>
            <View style={[s.trilhoGosto, { backgroundColor: c["surface-300"] }]}>
              <View style={[s.barraGosto, { width: porcentagem, backgroundColor: c.placa }]} />
            </View>
            <Text style={[estiloTexto("km"), s.porcentagem, { color: c["ink-muted"] }]}>{porcentagem}</Text>
          </View>
        );
      })}
    </View>
  );
}

/** Perfil e gosto (canvas Perfil): o que o app aprendeu, o resumo da triagem, intervalo padrão e tema. */
export default function Perfil() {
  const { c } = useCores();
  const margens = useSafeAreaInsets();
  const { escolha } = useEscolhaTema();
  const { dados, erro, carregando, tentarDeNovo } = useCarregar("perfil", obterPerfilGosto);
  const [perfil, setPerfil] = useState<PerfilGosto | null>(null);
  const [resumo, setResumo] = useState("");
  const [erroAjuste, setErroAjuste] = useState<string>();
  const [salvando, setSalvando] = useState(false);
  const abriu = useRef(false);

  useEffect(() => {
    if (!dados) return;
    // Recarregar ao voltar para a aba não apaga o que a pessoa está escrevendo no resumo.
    setResumo((atual) => (perfil && atual.trim() !== (perfil.resumo ?? "") ? atual : dados.resumo ?? ""));
    setPerfil(dados);
  }, [dados]); // só reage a dados novos da API; `perfil` aqui é o de antes deles

  // As decisões mudam nas outras abas: ao voltar para o Perfil, recarrega (a primeira vez já carregou).
  useFocusEffect(
    useCallback(() => {
      if (abriu.current) tentarDeNovo();
      abriu.current = true;
    }, [tentarDeNovo]),
  );

  async function ajustar(ajuste: AjustePerfil): Promise<PerfilGosto | null> {
    setErroAjuste(undefined);
    try {
      const novo = await ajustarPerfil(ajuste);
      setPerfil(novo);
      return novo;
    } catch (e) {
      setErroAjuste(mensagemDeErro(e));
      return null;
    }
  }

  function escolherIntervalo(km: number) {
    if (perfil) setPerfil({ ...perfil, intervalo_km: km }); // muda na hora; o erro avisa se não gravou
    void ajustar({ intervalo_km: km });
  }

  function escolherTema(tema: EscolhaTema) {
    definirTema(tema); // vale na hora e fica no aparelho, mesmo sem rede
    void ajustar({ tema });
  }

  async function salvarResumo() {
    setSalvando(true);
    const novo = await ajustar({ resumo });
    if (novo) setResumo(novo.resumo ?? "");
    setSalvando(false);
  }

  if (!perfil) {
    if (erro) return <Aviso mensagem={erro} acao="Tentar de novo" onAcao={tentarDeNovo} />;
    if (carregando) return <View style={{ flex: 1, backgroundColor: c["surface-100"] }} />;
  }

  const total = perfil?.total_swipes ?? 0;
  const aprendeu = total >= MINIMO_DECISOES;
  const resumoMudou = resumo.trim() !== (perfil?.resumo ?? "");

  return (
    <ScrollView
      style={{ backgroundColor: c["surface-100"] }}
      contentContainerStyle={[s.tela, { paddingTop: margens.top + espaco["space-8"] }]}
      keyboardShouldPersistTaps="handled"
    >
      <View style={s.cabecalho}>
        <Text accessibilityRole="header" style={[estiloTexto("display-xl"), { color: c.ink }]}>
          O que você <Destaque>curte</Destaque>
        </Text>
        <Text style={[estiloTexto("body"), { color: c["ink-muted"] }]}>
          {aprendeu
            ? `Aprendido com ${lugares(total)} que você deslizou. Usamos isso para ordenar os próximos cards.`
            : `Ainda estamos aprendendo seu gosto. Você avaliou ${lugares(total)}; a partir de ${MINIMO_DECISOES}, mostramos aqui o que você mais aceita.`}
        </Text>
        <Link href={{ pathname: "/triagem", params: { refazer: "1" } }} style={[estiloTexto("body-strong"), s.link, { color: c.placa }]}>
          Refazer as perguntas
        </Link>
      </View>

      {perfil && aprendeu ? <GostoAprendido perfil={perfil} /> : null}

      <View style={s.secao}>
        <TextField
          label="O que a IA entendeu de você"
          hint="Corrija se não for bem assim. A IA usa esse texto para ordenar os cards."
          placeholder="Conte como você gosta de viajar"
          value={resumo}
          onChangeText={setResumo}
          multiline
          maxLength={1000}
        />
        {resumoMudou ? (
          <Button size="sm" disabled={salvando} onPress={salvarResumo}>
            Salvar
          </Button>
        ) : null}
      </View>

      <View style={s.secao}>
        <Text accessibilityRole="header" style={[estiloTexto("title"), { color: c.ink }]}>
          Preferências
        </Text>
        <Text style={[estiloTexto("body-strong"), { color: c.ink }]}>Parar a cada</Text>
        <Segmented
          block
          rotulo="Distância padrão entre paradas"
          opcoes={INTERVALOS}
          valor={perfil?.intervalo_km ?? INTERVALO_PADRAO}
          onChange={escolherIntervalo}
        />
        <Text style={[estiloTexto("body-strong"), s.rotuloTema, { color: c.ink }]}>Tema</Text>
        <Segmented block rotulo="Tema" opcoes={TEMAS} valor={escolha} onChange={escolherTema} />
        {erroAjuste ? (
          <Text accessibilityRole="alert" style={[estiloTexto("body-s"), { color: c.perigo }]}>
            {erroAjuste}
          </Text>
        ) : null}
      </View>

      <SeusDados />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  tela: { gap: espaco["space-6"], paddingHorizontal: espaco["space-4"], paddingBottom: espaco["space-8"] },
  cabecalho: { gap: espaco["space-2"] },
  link: { alignSelf: "flex-start", minHeight: espaco.touch, textAlignVertical: "center" },
  gosto: { padding: espaco["space-4"], borderRadius: raio["radius-md"], gap: espaco["space-3"] },
  linhaGosto: { flexDirection: "row", alignItems: "center", gap: espaco["space-3"] },
  rotuloGosto: { width: medida.gostoRotulo, flexDirection: "row", alignItems: "center", gap: espaco["space-2"] },
  trilhoGosto: { flex: 1, height: medida.gostoBarra, borderRadius: raio["radius-pill"], overflow: "hidden" },
  barraGosto: { height: "100%", borderRadius: raio["radius-pill"] },
  porcentagem: { width: medida.gostoPorcentagem, textAlign: "right" },
  secao: { gap: espaco["space-2"] },
  rotuloTema: { marginTop: espaco["space-2"] },
  botoes: { flexDirection: "row", flexWrap: "wrap", gap: espaco["space-2"] },
});
