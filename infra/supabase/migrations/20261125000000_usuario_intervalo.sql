-- Issue #31: o intervalo padrão entre paradas que a pessoa escolhe no perfil (HU04 vai de 10 a 600 km).
-- Sem valor, o app usa o próprio padrão.
alter table public.usuario add column intervalo_km real check (intervalo_km between 10 and 600);
