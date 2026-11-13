import { Redirect } from "expo-router";
import { useState, type ReactNode } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { BottomNav, type Area } from "@/componentes/BottomNav";
import { Button } from "@/componentes/Button";
import { Ceu } from "@/componentes/Ceu";
import { categorias, Chip, type Categoria } from "@/componentes/Chip";
import { Destaque } from "@/componentes/Destaque";
import { Estrada } from "@/componentes/Estrada";
import { Icon, type IconName } from "@/componentes/Icon";
import { Rating } from "@/componentes/Rating";
import { PilhaSwipe } from "@/componentes/PilhaSwipe";
import { Segmented } from "@/componentes/Segmented";
import { StopItem } from "@/componentes/StopItem";
import { SwipeActions } from "@/componentes/SwipeActions";
import { SwipeCard, type CardLugar } from "@/componentes/SwipeCard";
import { TextField } from "@/componentes/TextField";
import { Toast } from "@/componentes/Toast";
import { espaco, estiloTexto, TemaProvider, useCores, type Tema } from "@/tema";

const exemplos: CardLugar[] = [
  {
    id: "exemplo:1", nome: "Churrascaria Gaúcha", categoria: "restaurante", cidade: "Lages", uf: "SC",
    foto: "https://picsum.photos/id/1080/760/1090", nota: 4.7, avaliacoes: 1834, km: 512, horas: 6.8,
    descricao: "Rodízio tradicional a 2 km da BR-116, aberto até as 23h.",
    instagram: "https://instagram.com/churrascariagaucha",
  },
  {
    id: "exemplo:2", nome: "Mirante do Vale", categoria: "turismo", foto: null, cidade: "Vitória da Conquista", uf: "BA",
    nota: 4.5, avaliacoes: 642, instagram: "@mirantedovale", instagramProvavel: true,
  },
  { id: "exemplo:3", nome: "Posto Serra Azul", categoria: "posto", cidade: "Montes Claros", uf: "MG", km: 2104, horas: 27, nota: 4.3, avaliacoes: 211 },
];

const icones: IconName[] = [
  "x", "check", "star", "pin", "camera", "food", "fuel", "leaf", "bed",
  "route", "compass", "user", "suitcase", "clock", "at", "car", "moto", "bike",
];

/** Catálogo dos componentes base nos dois temas. Só existe em desenvolvimento. */
export default function CatalogoComponentes() {
  if (!__DEV__) return <Redirect href="/" />;
  return (
    <SafeAreaView style={s.tela}>
      <ScrollView>
        {(["light", "dark"] as const).map((tema) => (
          <TemaProvider key={tema} tema={tema}>
            <Catalogo tema={tema} />
          </TemaProvider>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

function Catalogo({ tema }: { tema: Tema }) {
  const { c } = useCores();
  const [filtros, setFiltros] = useState<Categoria[]>(["turismo", "posto"]);
  const [area, setArea] = useState<Area>("descobrir");
  const [cidade, setCidade] = useState("");
  const nada = () => {};
  const [pilha, setPilha] = useState(exemplos);

  const alternar = (cat: Categoria) =>
    setFiltros((atual) => (atual.includes(cat) ? atual.filter((x) => x !== cat) : [...atual, cat]));

  return (
    <View style={[s.secao, { backgroundColor: c["surface-100"] }]}>
      <Text style={[estiloTexto("display-l"), { color: c.ink }]}>{tema === "light" ? "Claro" : "Escuro"}</Text>

      <Bloco titulo="Icon">
        <View style={s.linha}>
          {icones.map((nome) => (
            <Icon key={nome} name={nome} filled={nome === "star"} />
          ))}
        </View>
      </Bloco>

      <Bloco titulo="Button">
        <Button onPress={nada} icon="route" block>Montar roteiro</Button>
        <View style={s.linha}>
          <Button onPress={nada} variant="secondary">Editar paradas</Button>
          <Button onPress={nada} variant="ghost">Ver todos</Button>
        </View>
        <View style={s.linha}>
          <Button onPress={nada} variant="favorito" icon="star">Ver favoritos</Button>
          <Button onPress={nada} size="sm">Adicionar parada</Button>
          <Button onPress={nada} disabled>Desabilitado</Button>
        </View>
      </Bloco>

      <Bloco titulo="Chip">
        <View style={s.linha}>
          {(Object.keys(categorias) as Categoria[]).map((cat) => (
            <Chip key={cat} categoria={cat} />
          ))}
        </View>
        <View style={s.linha}>
          {(Object.keys(categorias) as Categoria[]).map((cat) => (
            <Chip key={cat} categoria={cat} selected={filtros.includes(cat)} onPress={() => alternar(cat)} />
          ))}
        </View>
        <View style={[s.linha, s.foto, { backgroundColor: c.asfalto }]}>
          <Chip categoria="restaurante" onPhoto />
          <Rating nota={4.7} avaliacoes={1834} onPhoto />
        </View>
      </Bloco>

      <Bloco titulo="TextField">
        <TextField label="De onde você sai?" icon="pin" placeholder="Cidade, UF" hint="Digite a cidade e escolha na lista" value={cidade} onChangeText={setCidade} />
        <TextField label="Para onde você vai?" icon="pin" placeholder="Cidade, UF" erro="Confira a grafia" defaultValue="Vitória da Conquita" />
      </Bloco>

      <Bloco titulo="Segmented">
        <Segmented
          rotulo="Como você vai"
          block
          opcoes={[
            { valor: "carro", label: "Carro", icon: "car" },
            { valor: "moto", label: "Moto", icon: "moto" },
            { valor: "bicicleta", label: "Bicicleta", icon: "bike" },
          ]}
        />
        <Segmented
          rotulo="Tema"
          padrao="sistema"
          opcoes={[
            { valor: "claro", label: "Claro" },
            { valor: "escuro", label: "Escuro" },
            { valor: "sistema", label: "Sistema" },
          ]}
        />
      </Bloco>

      <Bloco titulo="Ceu e Destaque">
        <Ceu serra>
          <Text style={[estiloTexto("display-xl"), { color: c.ink }]}>
            Para onde a <Destaque>estrada</Destaque> te leva?
          </Text>
          <Text style={[estiloTexto("body"), { color: c["ink-muted"] }]}>Lugares no caminho, escolhidos por você.</Text>
        </Ceu>
        <Ceu variante="placa" arredondado>
          <Text style={[estiloTexto("title"), { color: c.ink }]}>
            Seu roteiro está <Destaque>pronto</Destaque>
          </Text>
          <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>Variante placa, em bloco</Text>
        </Ceu>
      </Bloco>

      <Bloco titulo="Estrada">
        <Estrada cidades={["Alegrete", "Lages", "Curitiba", "São Paulo", "Vitória da Conquista"]} />
        <Estrada cidades={["Alegrete", "Lages", "Curitiba"]} variante="subida" parado />
      </Bloco>

      <Bloco titulo="StopItem">
        <View>
          <StopItem cidade="Alegrete" uf="RS" km={0} horas={0} tipo="origem" />
          <StopItem cidade="Lages" uf="SC" km={512} horas={6} ativo aceitos={3} total={12} />
          <StopItem cidade="Curitiba" uf="PR" km={1834} horas={22.5} aceitos={0} total={8} />
          <StopItem cidade="Vitória da Conquista" uf="BA" km={3120} horas={39} tipo="destino" />
        </View>
      </Bloco>

      <Bloco titulo="Rating">
        <View style={s.linha}>
          <Rating nota={4.7} avaliacoes={1834} />
          <Rating nota={5} avaliacoes={12} />
          <Rating nota={4.2} />
        </View>
      </Bloco>

      <Bloco titulo="SwipeCard">
        <SwipeCard card={exemplos[0]} />
        <SwipeCard card={exemplos[1]} stamp="bora" />
        <SwipeCard card={exemplos[2]} stamp="passo" />
      </Bloco>

      <Bloco titulo="SwipeActions">
        <SwipeActions onPasso={nada} onFavorito={nada} onBora={nada} />
        <SwipeActions onPasso={nada} onFavorito={nada} onBora={nada} disabled />
      </Bloco>

      <Bloco titulo="PilhaSwipe">
        <PilhaSwipe cards={pilha} onDecisao={(card) => setPilha((atual) => atual.filter((x) => x.id !== card.id))} />
        {pilha.length === 0 ? <Button onPress={() => setPilha(exemplos)} variant="secondary">Recomeçar</Button> : null}
      </Bloco>

      <Bloco titulo="Toast">
        <Toast acao="Desfazer" onAcao={nada}>Churrascaria Gaúcha entrou no roteiro</Toast>
        <Toast icon="star">Cachoeira do Tabuleiro virou favorito</Toast>
      </Bloco>

      <Bloco titulo="BottomNav">
        <BottomNav ativo={area} onChange={setArea} />
      </Bloco>
    </View>
  );
}

function Bloco({ titulo, children }: { titulo: string; children: ReactNode }) {
  const { c } = useCores();
  return (
    <View style={s.bloco}>
      <Text style={[estiloTexto("label"), { color: c["ink-muted"] }]}>{titulo.toUpperCase()}</Text>
      {children}
    </View>
  );
}

const s = StyleSheet.create({
  tela: { flex: 1 },
  secao: { padding: espaco["space-4"], gap: espaco["space-8"] },
  bloco: { gap: espaco["space-3"] },
  linha: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: espaco["space-2"] },
  foto: { padding: espaco["space-4"] },
});
