-- Issue #61: o perfil de gosto usa o card que a própria pessoa viu.
--
-- `lugar` é compartilhado e só o primeiro swipe grava o card (o /swipe não
-- reescreve mais). Para quem chegou primeiro não decidir a categoria, o tipo, a
-- faixa de preço e a nota que entram no perfil dos outros, a decisão guarda os
-- campos do card que o perfil usa. Decisões antigas (card nulo) usam o `lugar`.

alter table public.decisao add column card jsonb;
