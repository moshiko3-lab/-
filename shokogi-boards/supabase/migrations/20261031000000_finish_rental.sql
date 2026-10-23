-- Owner's request: "Mark returned" never ends a rental that has time left, for anyone; it only takes the boards
-- back (the rental stays under "Needs a board" until its time is up, then the timer ends it). Ending a rental early
-- is "Finish rental", the owner's alone, and the database holds everyone else to that.

-- Mark returned: every board back at the same instant; the rental ends only once its time is up.
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
  back := case when found then now() else (select max(unassigned_at) from public.rental_items where rental_id = p_rental) end;
  if r.due_at > now() then return; end if; -- time left: stays open for another board
  update public.rentals set ended_at = coalesce(back, now()), ended_by = auth.uid() where id = p_rental;
end $$;

-- Finish rental (owner): any boards back and the rental ends now, time left or not. As with a return, it counts as
-- returned when its boards came back, so History shows them.
create function public.finish_rental(p_rental uuid) returns void
language plpgsql set search_path = '' as $$
declare back timestamptz;
begin
  if not public.is_owner() then raise exception 'Only the owner can finish a rental.'; end if;
  update public.rental_items set unassigned_at = now(), unassigned_by = auth.uid()
  where rental_id = p_rental and unassigned_at is null;
  back := case when found then now() else (select max(unassigned_at) from public.rental_items where rental_id = p_rental) end;
  update public.rentals set ended_at = coalesce(back, now()), ended_by = auth.uid() where id = p_rental and ended_at is null;
  if not found then raise exception 'This rental was already returned.'; end if;
end $$;
revoke execute on function public.finish_rental from public, anon;
grant execute on function public.finish_rental to authenticated;

-- Only the owner ends a rental that still has time left, whatever the way in (the timer and server scripts,
-- with no signed-in person, only end rentals whose time is up).
create function public.rentals_finish_guard() returns trigger
language plpgsql set search_path = '' as $$
begin
  if old.ended_at is null and new.ended_at is not null and old.due_at > now()
     and auth.uid() is not null and not public.is_owner() then
    raise exception 'Only the owner can finish a rental before its time is up.';
  end if;
  return new;
end $$;
create trigger rentals_finish_guard before update on public.rentals
  for each row execute function public.rentals_finish_guard();
