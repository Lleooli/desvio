-- Issue #41: uso do Groq por modelo e por dia (UTC), para o alerta de 80% da cota.
-- Só o servidor lê e escreve: RLS ligada, sem política, e nada para anon/authenticated.

create table public.uso_ia (
  dia date not null,
  modelo text not null,
  chamadas integer not null default 0,
  tokens integer not null default 0,
  alertado boolean not null default false,
  primary key (dia, modelo)
);

alter table public.uso_ia enable row level security;
revoke all on public.uso_ia from anon, authenticated;
