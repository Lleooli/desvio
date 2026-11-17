-- A decisão só aponta para uma viagem da própria pessoa.
--
-- A política antiga conferia só `usuario`: pelo PostgREST, alguém podia gravar
-- uma decisão com o id da viagem de outra pessoa (descobrindo que o id existe e
-- prendendo a linha ao cascade da viagem alheia).

drop policy "decisao: as próprias" on public.decisao;

create policy "decisao: as próprias" on public.decisao
  for all to authenticated
  using (usuario = (select auth.uid()))
  with check (
    usuario = (select auth.uid())
    and (viagem is null
         or exists (select 1 from public.viagem v where v.id = viagem and v.usuario = (select auth.uid())))
  );
