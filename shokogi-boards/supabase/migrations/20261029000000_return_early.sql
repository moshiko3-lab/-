-- Owner's request: a customer who brings the boards back before their rental time is up may take another board
-- until it ends (a 3-day rental, one board a day). So "Mark returned" with time left takes the boards back and keeps
-- the rental open, under "Needs a board". With no board out, or once the time is up, it ends the rental.
-- An ended rental counts as returned when its boards came back: History shows those boards (they were closed at
-- ended_at exactly) and it isn't late.
create or replace function public.return_rental(p_rental uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare
  r public.rentals;
  back timestamptz;
begin
  if not public.is_member() then raise exception 'Sign in first.'; end if;
  select * into r from public.rentals where id = p_rental and ended_at is null for update;
  if not found then raise exception 'This rental was already returned.'; end if;
  update public.rental_items set unassigned_at = now(), unassigned_by = auth.uid()
  where rental_id = p_rental and unassigned_at is null;
  if found then
    if r.due_at > now() then return; end if; -- time left: stays open for another board
    back := now();
  else
    back := (select max(unassigned_at) from public.rental_items where rental_id = p_rental); -- brought back earlier
  end if;
  update public.rentals set ended_at = coalesce(back, now()), ended_by = auth.uid() where id = p_rental;
end $$;

-- Ends the rentals whose time is up with no board out (returned early, or never given one), as returned when the
-- last board came back, by whoever took it back. A database timer runs it every minute.
create function public.end_finished_rentals() returns void
language sql set search_path = '' as $$
  update public.rentals r
  set ended_at = coalesce(last.unassigned_at, r.due_at), ended_by = last.unassigned_by
  from public.rentals r2
  left join lateral (select i.unassigned_at, i.unassigned_by from public.rental_items i
                     where i.rental_id = r2.id order by i.unassigned_at desc nulls last limit 1) last on true
  where r.id = r2.id and r.ended_at is null and r.due_at <= now()
    and not exists (select 1 from public.rental_items i where i.rental_id = r.id and i.unassigned_at is null)
$$;
revoke execute on function public.end_finished_rentals from public, anon, authenticated;
grant execute on function public.end_finished_rentals to service_role;

select cron.schedule('end-finished-rentals', '* * * * *', 'select public.end_finished_rentals()');
