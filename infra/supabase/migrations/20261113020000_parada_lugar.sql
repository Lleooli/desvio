-- Issue #4: a viagem guardada no banco, com os cards de cada parada.
--
-- Quando o job termina, o worker grava a viagem, as paradas e os lugares
-- (app/viagens.py). O card em si fica em `lugar` (compartilhado); a ligação
-- de cada parada com seus lugares, na ordem da coleta e com o km daquela
-- rota, fica em `parada_lugar`. `parada.dados` guarda o que a tela usa e não
-- tem coluna própria (lat, lon, tipo, avisos).

alter table public.parada add column dados jsonb not null default '{}';

create table public.parada_lugar (
  viagem uuid not null,
  parada int not null,
  lugar text not null references public.lugar (id) on delete cascade,
  posicao int not null,
  km_na_rota real,
  horas_desde_saida real,
  primary key (viagem, parada, lugar),
  foreign key (viagem, parada) references public.parada (viagem, ordem) on delete cascade
);
create index parada_lugar_lugar on public.parada_lugar (lugar);

alter table public.parada_lugar enable row level security;

create policy "parada_lugar: das próprias viagens" on public.parada_lugar
  for select to authenticated
  using (exists (select 1 from public.viagem v where v.id = viagem and v.usuario = (select auth.uid())));

-- só o servidor grava (o worker); o app só lê
grant select on public.parada_lugar to authenticated;
revoke insert, update, delete, truncate on public.parada_lugar from anon, authenticated;
revoke all on public.parada_lugar from anon;
