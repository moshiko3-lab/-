-- Instructors hand out one board per rental; a further board (a family) is for the desk (owner's request).
-- Swapping stays allowed: a board taken back on this rental in the same transaction (assign_board with p_replace)
-- makes room for the new one. Otherwise the same hand-out guard as 20261026000000_quantity.
create or replace function public.rental_items_guard() returns trigger
language plpgsql security definer set search_path = '' as $$
declare b public.boards;
begin
  if new.unassigned_at is not null then return new; end if;
  if auth.uid() is not null and not public.is_desk()
     and exists (select 1 from public.rental_items where rental_id = new.rental_id and unassigned_at is null)
     and not exists (select 1 from public.rental_items where rental_id = new.rental_id and unassigned_at = now()) then
    raise exception 'This customer already has a board. Ask the desk to add another one.';
  end if;
  select * into b from public.boards where id = new.board_id for update;
  if b.deleted_at is not null or b.in_repair >= b.quantity then raise exception 'This board is not available.'; end if;
  if exists (select 1 from public.rentals where id = new.rental_id and ended_at is not null) then
    raise exception 'This rental has already ended.';
  end if;
  if (select count(*) from public.rental_items where board_id = new.board_id and unassigned_at is null) + b.in_repair >= b.quantity then
    raise exception 'This board was just taken by someone else. Choose another one.';
  end if;
  return new;
end $$;
