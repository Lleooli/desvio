import { StyleSheet, Text, View } from "react-native";
import { espaco, estiloTexto, fontes, medida, raio, useCores } from "@/tema";
import { numero } from "./Rating";

type Props = {
  cidade: string;
  uf?: string;
  /** km na rota (modo carro). */
  km?: number;
  /** Horas de estrada desde a saída; 0 é a saída (modo carro). */
  horas?: number;
  /** Dias na cidade (modo avião, no lugar de km e horas). */
  dias?: number;
  tipo?: "origem" | "parada" | "destino";
  /** A parada que está sendo escolhida agora. */
  ativo?: boolean;
  /** Cards aceitos sobre os mostrados: "3 de 12". */
  aceitos?: number;
  total?: number;
};

/**
 * Uma linha da linha do tempo da viagem. Empilhe vários em sequência: o trilho se
 * conecta sozinho. Quem usa decide o que o toque abre (o swipe daquela parada).
 */
export function StopItem({ cidade, uf, km, horas, dias, tipo = "parada", ativo = false, aceitos = 0, total }: Props) {
  const { c } = useCores();

  const nome = uf ? `${cidade}, ${uf}` : cidade;
  const rotuloKm = km != null ? `KM ${numero(km)}` : "";
  const detalhes: string[] = [];
  if (horas != null) detalhes.push(horas === 0 ? "Saída" : `~${numero(horas, horas % 1 ? 1 : 0)}h de estrada`);
  if (dias) detalhes.push(dias > 1 ? `${dias} dias` : "1 dia");
  const contagem = total != null ? `${aceitos} de ${total}` : null;

  const pontaDaViagem = tipo === "origem" || tipo === "destino";
  const ponto = ativo
    ? { backgroundColor: c.faixa, borderColor: c["on-faixa"] }
    : pontaDaViagem
      ? { backgroundColor: c.placa, borderColor: c.placa }
      : { backgroundColor: c["surface-200"], borderColor: c["ink-muted"] };

  const leitura = [rotuloKm, nome, ...detalhes, contagem, ativo ? "parada atual" : null].filter(Boolean).join(", ");

  return (
    <View accessible accessibilityLabel={leitura} style={s.linha}>
      <Text style={[estiloTexto("km"), s.km, { color: ativo ? c.ink : c["ink-muted"] }]}>{rotuloKm}</Text>
      <View style={s.trilho}>
        <View style={[s.linhaTrilho, { backgroundColor: c["surface-300"] }]} />
        <View style={[s.ponto, ponto]} />
      </View>
      <View style={s.info}>
        <Text style={[estiloTexto("body-strong"), { color: c.ink }]}>{nome}</Text>
        {detalhes.length ? (
          <Text style={[estiloTexto("body-s"), { color: c["ink-muted"] }]}>{detalhes.join(" · ")}</Text>
        ) : null}
      </View>
      {contagem ? <Text style={[estiloTexto("body-s"), s.contagem, { color: c.placa }]}>{contagem}</Text> : null}
    </View>
  );
}

const s = StyleSheet.create({
  linha: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: espaco["space-2"],
    minHeight: medida.paradaAltura,
  },
  km: { width: medida.paradaKm, paddingTop: medida.paradaAjusteTopo, textAlign: "right", textTransform: "uppercase" },
  trilho: { width: medida.paradaTrilho, alignSelf: "stretch", alignItems: "center" },
  linhaTrilho: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: medida.paradaTrilhoLinha,
    borderRadius: raio["radius-pill"],
  },
  ponto: {
    marginTop: espaco["space-1"],
    width: medida.paradaPonto,
    height: medida.paradaPonto,
    borderRadius: raio["radius-pill"],
    borderWidth: medida.paradaPontoBorda,
  },
  info: { flex: 1, paddingBottom: espaco["space-3"] },
  contagem: { paddingTop: medida.paradaAjusteTopo, fontFamily: fontes.sansForte },
});
