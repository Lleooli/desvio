/**
 * Duração de estrada como a pessoa fala: "45 min", "2h", "1h48". Nunca "1,8h": ninguém
 * lê décimo de hora.
 *
 * @param horas - A duração em horas, como vem do coletor (`horas_desde_saida`).
 */
export function duracao(horas: number): string {
  const total = Math.max(0, Math.round(horas * 60));
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h}h` : `${h}h${String(m).padStart(2, "0")}`;
}
