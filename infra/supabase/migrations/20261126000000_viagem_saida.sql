-- Issue #104: hora de saída e data (opcional) da viagem, escolhidas na Nova viagem.
-- A coleta usa a saída para planejar onde a pessoa dorme; o roteiro usa as duas como
-- contexto padrão. Viagens de antes ficam sem (null): valem 07:00 e sem data.
alter table public.viagem
  add column saida text check (saida ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'),
  add column data date;
