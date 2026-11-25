-- Issue #30: a pessoa edita o roteiro. Os lugares que ela tirou ficam aqui, para o roteiro
-- montado de novo não trazê-los de volta; a decisão Bora deles continua em `decisao`.
alter table public.roteiro add column removidos text[] not null default '{}';
