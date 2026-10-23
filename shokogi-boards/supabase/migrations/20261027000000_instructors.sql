-- Instructors: a third role with one job. They hand boards to customers, swap or take them back and mark rentals
-- returned. They read only open rentals, see customers by name only (no phone, email or notes), and change nothing
-- else: no new rentals, return times, customers, boards, photos or settings.

alter table public.profiles drop constraint profiles_role_check;
alter table public.profiles add constraint profiles_role_check check (role in ('owner', 'staff', 'instructor'));

-- Owner and desk staff: everyday work beyond handing out boards.
create function public.is_desk() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles where id = auth.uid() and active and role in ('owner', 'staff'))
$$;

drop policy "members add boards" on public.boards;
drop policy "members edit boards" on public.boards;
create policy "desk adds boards" on public.boards for insert to authenticated with check (public.is_desk());
create policy "desk edits boards" on public.boards for update to authenticated using (public.is_desk());

drop policy "members read customers" on public.customers;
drop policy "members add customers" on public.customers;
drop policy "members edit customers" on public.customers;
create policy "desk reads customers" on public.customers for select to authenticated using (public.is_desk());
create policy "desk adds customers" on public.customers for insert to authenticated with check (public.is_desk());
create policy "desk edits customers" on public.customers for update to authenticated using (public.is_desk());

drop policy "members read rentals" on public.rentals;
drop policy "members add rentals" on public.rentals;
drop policy "members edit rentals" on public.rentals;
create policy "desk reads rentals, instructors open ones" on public.rentals for select to authenticated
  using (public.is_desk() or (ended_at is null and public.is_member()));
create policy "desk adds rentals" on public.rentals for insert to authenticated with check (public.is_desk());
create policy "desk edits rentals" on public.rentals for update to authenticated using (public.is_desk());

drop policy "members read settings" on public.app_settings;
create policy "desk reads settings" on public.app_settings for select to authenticated using (public.is_desk());

drop policy "members upload board photos" on storage.objects;
drop policy "members replace board photos" on storage.objects;
drop policy "members remove board photos" on storage.objects;
create policy "desk uploads board photos" on storage.objects for insert to authenticated with check (bucket_id = 'boards' and public.is_desk());
create policy "desk replaces board photos" on storage.objects for update to authenticated using (bucket_id = 'boards' and public.is_desk());
create policy "desk removes board photos" on storage.objects for delete to authenticated using (bucket_id = 'boards' and public.is_desk());

-- The hand-out guard must see every rental and lock the board row, which an instructor's own permissions don't allow
-- (ended rentals are hidden from them, boards aren't theirs to update).
alter function public.rental_items_guard() security definer;

-- Instructors may end a rental but not edit rentals, so returning runs with full rights for any active member.
create or replace function public.return_rental(p_rental uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_member() then raise exception 'Sign in first.'; end if;
  update public.rentals set ended_at = now(), ended_by = auth.uid() where id = p_rental and ended_at is null;
  if not found then raise exception 'This rental was already returned.'; end if;
  update public.rental_items set unassigned_at = now(), unassigned_by = auth.uid()
  where rental_id = p_rental and unassigned_at is null;
end $$;

-- The customer names on open rentals: all an instructor learns about customers.
create function public.open_rental_names() returns table (rental_id uuid, name text)
language sql stable security definer set search_path = '' as $$
  select r.id, c.name from public.rentals r join public.customers c on c.id = r.customer_id
  where r.ended_at is null and public.is_member()
$$;
revoke execute on function public.open_rental_names from public, anon;
grant execute on function public.open_rental_names to authenticated;
