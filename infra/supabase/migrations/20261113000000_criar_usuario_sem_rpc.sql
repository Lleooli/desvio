-- criar_usuario() é security definer e só serve ao trigger ao_criar_conta.
-- Sem este revoke, o PostgREST a expõe em /rest/v1/rpc/criar_usuario para anon
-- e authenticated (aviso do Security Advisor do Supabase). O trigger continua
-- funcionando: quem dispara é o insert em auth.users, não um papel da API.
revoke execute on function public.criar_usuario() from public, anon, authenticated;
