-- Issue #39 (HU07): token do Expo Push, para avisar quando a busca termina.
--
-- A coluna fica em `usuario`, então vale a política que já existe: a pessoa só lê
-- e escreve a própria linha. Quem grava no fluxo normal é a API (dona da tabela).
-- O valor é o token do aparelho, não e-mail nem nome.

alter table public.usuario add column expo_push_token text
  check (
    expo_push_token is null
    or expo_push_token ~ '^(Exponent|Expo)PushToken\[[A-Za-z0-9_-]{8,200}\]$'
  );
