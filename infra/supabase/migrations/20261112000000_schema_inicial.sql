-- Schema inicial do Desvio (PRD, "Modelo de dados").
--
-- Quem escreve aqui é a API e o worker, conectados como dono das tabelas
-- (PV_DATABASE_URL), o que passa por cima da RLS. A RLS protege o acesso direto
-- com a chave anônima: cada pessoa só lê e escreve o que é dela; `lugar` é
-- leitura pública; `jobs` só leitura do dono; `cache` fica fechado.

create extension if not exists pgcrypto;

-- usuario: espelho de auth.users com o que o app precisa
create table public.usuario (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  provedor text,
  perfil_gosto jsonb,
  tema text not null default 'sistema' check (tema in ('claro', 'escuro', 'sistema')),
  criado_em timestamptz not null default now()
);

-- Toda conta nova no Supabase Auth ganha a linha em usuario
create function public.criar_usuario() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.usuario (id, email, provedor)
  values (new.id, new.email, new.raw_app_meta_data ->> 'provider')
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger ao_criar_conta after insert on auth.users
  for each row execute function public.criar_usuario();

create table public.viagem (
  id uuid primary key default gen_random_uuid(),
  usuario uuid not null references public.usuario (id) on delete cascade,
  veiculo text not null default 'carro' check (veiculo in ('carro', 'moto', 'bicicleta')),
  origem text not null,
  destino text not null,
  intervalo_km real not null,
  categorias text[] not null default '{}',
  status text not null default 'buscando' check (status in ('buscando', 'escolhendo', 'pronta', 'falhou')),
  polilinha text,
  job text,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);
create index viagem_usuario on public.viagem (usuario, criado_em desc);

create table public.parada (
  viagem uuid not null references public.viagem (id) on delete cascade,
  ordem int not null,
  cidade text not null,
  uf text,
  km real,
  horas_desde_saida real,
  primary key (viagem, ordem)
);

-- lugar: o card, compartilhado entre pessoas (id gmaps:… ou osm:…)
create table public.lugar (
  id text primary key,
  dados jsonb not null,
  fonte text,
  coletado_em timestamptz not null default now()
);

create table public.decisao (
  usuario uuid not null references public.usuario (id) on delete cascade,
  lugar text not null references public.lugar (id) on delete cascade,
  viagem uuid references public.viagem (id) on delete cascade,
  parada int,
  tipo text not null check (tipo in ('bora', 'passo', 'favorito')),
  quando timestamptz not null default now(),
  primary key (usuario, lugar)
);
create index decisao_viagem on public.decisao (viagem);

create table public.roteiro (
  viagem uuid primary key references public.viagem (id) on delete cascade,
  itens jsonb not null default '[]',
  explicacao jsonb,
  fonte text,
  atualizado_em timestamptz not null default now()
);

-- jobs: fila da coleta (app/fila.py). O worker pega com FOR UPDATE SKIP LOCKED.
create table public.jobs (
  id text primary key,
  usuario uuid references public.usuario (id) on delete cascade,
  tipo text not null,
  entrada jsonb not null,
  status text not null default 'pendente' check (status in ('pendente', 'rodando', 'pronto', 'falhou')),
  resultado jsonb,
  parcial jsonb,
  progresso jsonb,
  erro text,
  criado_em timestamptz not null default clock_timestamp(),
  atualizado_em timestamptz not null default clock_timestamp()
);
create index jobs_pendentes on public.jobs (criado_em) where status = 'pendente';
create index jobs_usuario on public.jobs (usuario);

-- cache da coleta (app/cache.py): só o servidor usa
create table public.cache (
  chave text primary key,
  valor jsonb not null,
  guardado_em timestamptz not null default now()
);

-- RLS
alter table public.usuario enable row level security;
alter table public.viagem enable row level security;
alter table public.parada enable row level security;
alter table public.lugar enable row level security;
alter table public.decisao enable row level security;
alter table public.roteiro enable row level security;
alter table public.jobs enable row level security;
alter table public.cache enable row level security;

create policy "usuario: o próprio" on public.usuario
  for all to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

create policy "viagem: as próprias" on public.viagem
  for all to authenticated
  using (usuario = (select auth.uid())) with check (usuario = (select auth.uid()));

create policy "parada: das próprias viagens" on public.parada
  for all to authenticated
  using (exists (select 1 from public.viagem v where v.id = viagem and v.usuario = (select auth.uid())))
  with check (exists (select 1 from public.viagem v where v.id = viagem and v.usuario = (select auth.uid())));

create policy "lugar: leitura pública" on public.lugar
  for select to anon, authenticated using (true);

create policy "decisao: as próprias" on public.decisao
  for all to authenticated
  using (usuario = (select auth.uid())) with check (usuario = (select auth.uid()));

create policy "roteiro: das próprias viagens" on public.roteiro
  for all to authenticated
  using (exists (select 1 from public.viagem v where v.id = viagem and v.usuario = (select auth.uid())))
  with check (exists (select 1 from public.viagem v where v.id = viagem and v.usuario = (select auth.uid())));

create policy "jobs: leitura dos próprios" on public.jobs
  for select to authenticated using (usuario = (select auth.uid()));

grant usage on schema public to anon, authenticated;
grant select on public.lugar to anon;
grant select, insert, update, delete on public.usuario, public.viagem, public.parada,
  public.decisao, public.roteiro to authenticated;
grant select on public.lugar, public.jobs to authenticated;
-- o Supabase dá todos os privilégios a anon/authenticated por padrão; aqui tiramos o que só o servidor faz
revoke insert, update, delete, truncate on public.lugar, public.jobs from anon, authenticated;
revoke all on public.cache from anon, authenticated;
revoke all on public.usuario, public.viagem, public.parada, public.decisao, public.roteiro from anon;
