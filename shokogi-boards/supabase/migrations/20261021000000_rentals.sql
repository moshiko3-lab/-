-- Rental actions as single database transactions, so a lost connection or two devices at once
-- can never leave a rental half-done. They run as the caller: Row Level Security still applies.

-- The customer for a new rental: same phone digits ("050-123-4567" = "0501234567"), or, without a phone,
-- the same name (case-insensitive); otherwise a new customer.
create function public.upsert_customer(p_name text, p_phone text) returns uuid
language plpgsql set search_path = '' as $$
declare
  name_ text := btrim(coalesce(p_name, ''));
  digits text := regexp_replace(coalesce(p_phone, ''), '\D', '', 'g');
  cid uuid;
begin
  if name_ = '' then raise exception 'A customer needs a name.'; end if;
  if digits = '' then
    select id into cid from public.customers where lower(btrim(name)) = lower(name_) order by created_at desc limit 1;
    if cid is null then insert into public.customers (name) values (name_) returning id into cid; end if;
    return cid;
  end if;
  insert into public.customers (name, phone) values (name_, btrim(p_phone))
    on conflict (phone_digits) where phone_digits <> '' do nothing returning id into cid;
  if cid is null then select id into cid from public.customers where phone_digits = digits; end if;
  return cid;
end $$;

create function public.create_rental(p_name text, p_phone text, p_minutes int) returns uuid
language plpgsql set search_path = '' as $$
declare rid uuid;
begin
  if coalesce(p_minutes, 0) <= 0 then raise exception 'Choose a rental length.'; end if;
  insert into public.rentals (customer_id, due_at)
  values (public.upsert_customer(p_name, p_phone), now() + make_interval(mins => p_minutes))
  returning id into rid;
  return rid;
end $$;

-- Hands a board to a rental. With p_replace it's a swap: that hand-out is closed (kept for history) and the
-- new one opened in the same moment. If someone else just took the board, nothing changes (unique violation).
create function public.assign_board(p_rental uuid, p_board uuid, p_replace uuid default null) returns void
language plpgsql set search_path = '' as $$
begin
  if p_replace is not null then
    update public.rental_items set unassigned_at = now(), unassigned_by = auth.uid()
    where rental_id = p_rental and board_id = p_replace and unassigned_at is null;
  end if;
  insert into public.rental_items (rental_id, board_id) values (p_rental, p_board);
end $$;

create function public.remove_board(p_rental uuid, p_board uuid) returns void
language plpgsql set search_path = '' as $$
begin
  update public.rental_items set unassigned_at = now(), unassigned_by = auth.uid()
  where rental_id = p_rental and board_id = p_board and unassigned_at is null;
end $$;

-- Returning ends the rental and closes every board on it at the same instant.
create function public.return_rental(p_rental uuid) returns void
language plpgsql set search_path = '' as $$
begin
  update public.rentals set ended_at = now(), ended_by = auth.uid() where id = p_rental and ended_at is null;
  if not found then raise exception 'This rental was already returned.'; end if;
  update public.rental_items set unassigned_at = now(), unassigned_by = auth.uid()
  where rental_id = p_rental and unassigned_at is null;
end $$;

revoke execute on function public.upsert_customer, public.create_rental, public.assign_board, public.remove_board, public.return_rental from public, anon;
grant execute on function public.upsert_customer, public.create_rental, public.assign_board, public.remove_board, public.return_rental to authenticated;

-- Customers with their totals, for the Customers page (search runs on `search`).
create view public.customer_stats with (security_invoker = true) as
select c.id, c.name, c.phone, c.email, c.notes,
       lower(c.name || ' ' || c.phone || ' ' || c.phone_digits) as search,
       count(r.id)::int as rentals,
       coalesce(round(extract(epoch from sum(r.ended_at - r.starts_at)) / 3600), 0)::int as hours,
       count(*) filter (where r.ended_at > r.due_at)::int as late_returns,
       min(r.starts_at) as first_visit,
       max(r.starts_at) as last_visit,
       coalesce(bool_or(r.id is not null and r.ended_at is null), false) as renting_now
from public.customers c
left join public.rentals r on r.customer_id = c.id
group by c.id;

grant select on public.customer_stats to authenticated;
