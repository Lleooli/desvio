-- Issue #43: eventos de produto para as metas do PRD.
--
-- Só o servidor lê e escreve (a API, com PV_DATABASE_URL). A RLS fica ligada e
-- sem política, como `uso_ia`: o app não acessa a tabela pelo PostgREST.
-- O que identifica a pessoa é `usuario`; `dados` só leva metadado técnico
-- (tipo da decisão, ordem do card, tempo em ms, app de mapas).

create table public.evento (
  id uuid primary key default gen_random_uuid(),
  usuario uuid not null references public.usuario (id) on delete cascade,
  viagem uuid references public.viagem (id) on delete cascade,
  evento text not null check (evento in (
    'viagem_criada', 'primeiro_card', 'swipe', 'roteiro_montado',
    'roteiro_aberto_mapa', 'triagem_concluida', 'triagem_pulada'
  )),
  dados jsonb not null default '{}',
  criado_em timestamptz not null default now()
);

create index evento_usuario on public.evento (usuario, evento);
create index evento_viagem on public.evento (viagem) where viagem is not null;

alter table public.evento enable row level security;
revoke all on public.evento from anon, authenticated;
