-- Issue #40 (LGPD): conta apagada pelo app.
--
-- `DELETE /eu` apaga na hora os dados da pessoa no schema public e depois pede
-- ao Supabase (Admin API, com a service_role) que apague a linha em auth.users.
-- Se esse pedido falha, a conta fica aqui até o worker conseguir (app/conta.py),
-- no prazo de 15 dias. Enquanto estiver aqui, o token antigo responde 401 e a
-- API não recria a linha em `usuario`.
--
-- Sem chave estrangeira: a linha em `usuario` já foi apagada quando esta é criada.

create table public.exclusao_pendente (
  usuario uuid primary key,
  pedido_em timestamptz not null default now(),
  tentativas int not null default 0,
  ultimo_erro text,
  tentado_em timestamptz
);

-- só o servidor lê e grava
alter table public.exclusao_pendente enable row level security;
revoke all on public.exclusao_pendente from anon, authenticated;
