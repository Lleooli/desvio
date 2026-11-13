import { Pressable, StyleSheet, Text, View } from "react-native";
import { espaco, estiloTexto, medida, raio, tamanhoIcone, useCores } from "@/tema";
import { useFoco } from "./foco";
import { Icon, type IconName } from "./Icon";
import type { Decisao } from "./SwipeCard";

type Props = {
  onPasso: () => void;
  onFavorito: () => void;
  onBora: () => void;
  /** Enquanto o próximo card carrega ou o atual ainda está saindo. */
  disabled?: boolean;
};

/** Os três botões de decisão abaixo do card. Fazem o mesmo que o gesto; nunca dependa só dele. */
export function SwipeActions({ onPasso, onFavorito, onBora, disabled = false }: Props) {
  return (
    <View accessibilityRole="toolbar" accessibilityLabel="Decidir sobre este lugar" style={s.grupo}>
      <Acao decisao="passo" icone="x" rotulo="Passo" onPress={onPasso} disabled={disabled} />
      <Acao decisao="favorito" icone="star" rotulo="Favorito" onPress={onFavorito} disabled={disabled} />
      <Acao decisao="bora" icone="check" rotulo="Bora" onPress={onBora} disabled={disabled} />
    </View>
  );
}

type AcaoProps = { decisao: Decisao; icone: IconName; rotulo: string; onPress: () => void; disabled: boolean };

function Acao({ decisao, icone, rotulo, onPress, disabled }: AcaoProps) {
  const { c, sombra } = useCores();
  const foco = useFoco();
  // Bora (placa) e Passo (contorno ink) se distinguem por claridade; Passo não é vermelho.
  const visual = {
    passo: { fundo: c["surface-200"], cor: c.ink, borda: c.ink, sombra: sombra["shadow-2"] },
    favorito: { fundo: c.faixa, cor: c["on-faixa"], borda: c.faixa, sombra: sombra["shadow-favorito"] },
    bora: { fundo: c.placa, cor: c["on-placa"], borda: c.placa, sombra: sombra["shadow-2"] },
  }[decisao];
  const favorito = decisao === "favorito";
  const tamanho = favorito ? medida.botaoFavorito : medida.botaoSwipe;

  return (
    <View style={s.item}>
      <Pressable
        onPress={onPress}
        disabled={disabled}
        {...foco.eventos}
        accessibilityRole="button"
        accessibilityLabel={rotulo}
        aria-disabled={disabled}
        style={({ pressed }) => [
          s.botao,
          {
            width: tamanho,
            height: tamanho,
            backgroundColor: visual.fundo,
            borderColor: visual.borda,
            boxShadow: disabled ? undefined : visual.sombra,
          },
          favorito && s.favorito,
          foco.estilo,
          pressed && { transform: [{ scale: medida.pressionadoRedondo }] },
          disabled && { opacity: medida.desabilitado },
        ]}
      >
        <Icon
          name={icone}
          size={favorito ? tamanhoIcone.nav : tamanhoIcone.swipe}
          color={visual.cor}
          filled={favorito}
        />
      </Pressable>
      <Text aria-hidden style={[estiloTexto("label"), { color: c.ink }]}>
        {rotulo}
      </Text>
    </View>
  );
}

const s = StyleSheet.create({
  grupo: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "flex-start",
    gap: espaco["space-6"],
    padding: espaco["space-4"],
  },
  item: { alignItems: "center", gap: espaco["space-1"] },
  botao: {
    alignItems: "center",
    justifyContent: "center",
    borderRadius: raio["radius-pill"],
    borderWidth: medida.bordaSwipe,
  },
  // O Favorito é menor; a margem alinha o centro dele com o dos outros dois.
  favorito: { marginTop: (medida.botaoSwipe - medida.botaoFavorito) / 2 },
});
