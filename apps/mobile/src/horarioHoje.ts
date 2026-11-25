// O horário de hoje de um lugar como a folha do lugar mostra (HU11). O coletor já escolhe o
// dia no fuso do lugar; aqui só vira frase.

const FAIXA = /^(\d{2}):(\d{2})–(\d{2}):(\d{2})$/;
const DIA_INTEIRO = "00:00–24:00";

/** "11:30" -> "11h30"; "23:00" -> "23h"; "08:00" -> "8h". */
function hora(h: string, m: string): string {
  return `${Number(h)}h${m === "00" ? "" : m}`;
}

/** "11:30–23:00" -> "11h30 às 23h"; o que não está nesse formato sai como veio. */
function faixa(texto: string): string {
  const achado = FAIXA.exec(texto);
  return achado ? `${hora(achado[1], achado[2])} às ${hora(achado[3], achado[4])}` : texto;
}

/**
 * A frase do horário de hoje.
 *
 * @param faixas - O `horario_hoje` do card.
 * @returns "Aberto hoje, 11h30 às 23h", "Fechado hoje", "Aberto 24 horas hoje", ou null
 *   quando o horário de hoje não é conhecido.
 */
export function textoHorarioHoje(faixas?: string[] | null): string | null {
  if (faixas == null) return null;
  if (faixas.length === 0) return "Fechado hoje";
  if (faixas.includes(DIA_INTEIRO)) return "Aberto 24 horas hoje";
  return `Aberto hoje, ${faixas.map(faixa).join(" e ")}`;
}
