-- Identical boards under one name: a board has `quantity` copies, `in_repair` of them are in repair, and it can be
-- out on as many rentals at once (one family may take several) as it has free copies.

alter table public.boards add column quantity int not null default 1 check (quantity between 1 and 999);
alter table public.boards alter column in_repair drop default;
alter table public.boards alter column in_repair type int using in_repair::int; -- true = 1 of 1 in repair
alter table public.boards alter column in_repair set default 0;
alter table public.boards add constraint boards_in_repair_count check (in_repair between 0 and quantity);

-- One current hand-out per board no longer holds; the hand-out guard below counts copies instead.
drop index public.rental_items_one_current_per_board;
create index rental_items_current_idx on public.rental_items (board_id) where unassigned_at is null;

-- A board is handed out only on an active rental and only while a copy is free. Locking the board row makes two
-- devices taking its last free copy go one after the other, so the second one is refused.
-- (Past items, e.g. from the data import, are not checked.)
create or replace function public.rental_items_guard() returns trigger
language plpgsql set search_path = '' as $$
declare b public.boards;
begin
  if new.unassigned_at is not null then return new; end if;
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

-- Only the owner deletes boards, and never while a copy is out. Repairs and a lower quantity must leave room
-- for the copies that are out. (auth.uid() is null for server-side scripts, which are trusted.)
create or replace function public.boards_guard() returns trigger
language plpgsql set search_path = '' as $$
declare out_ int := (select count(*) from public.rental_items where board_id = new.id and unassigned_at is null);
begin
  if new.deleted_at is distinct from old.deleted_at then
    if auth.uid() is not null and not public.is_owner() then raise exception 'Only the owner can delete boards.'; end if;
    if new.deleted_at is not null and out_ > 0 then raise exception 'This board is rented. Mark it returned first.'; end if;
  end if;
  if out_ + new.in_repair > new.quantity and (new.in_repair > old.in_repair or new.quantity < old.quantity) then
    if new.quantity < old.quantity then
      raise exception '% of these boards are rented or in repair right now.', out_ + new.in_repair;
    end if;
    raise exception 'This board is rented. Mark it returned first.';
  end if;
  return new;
end $$;

-- Takes back one board: one copy, when the rental has several of the same.
create or replace function public.remove_board(p_rental uuid, p_board uuid) returns void
language plpgsql set search_path = '' as $$
begin
  update public.rental_items set unassigned_at = now(), unassigned_by = auth.uid()
  where id = (select id from public.rental_items where rental_id = p_rental and board_id = p_board and unassigned_at is null
              order by assigned_at desc limit 1);
end $$;

-- Hands a board to a rental. With p_replace it's a swap: one copy of that board is taken back (kept for history)
-- in the same moment. If the last free copy was just taken elsewhere, nothing changes.
create or replace function public.assign_board(p_rental uuid, p_board uuid, p_replace uuid default null) returns void
language plpgsql set search_path = '' as $$
begin
  if p_replace is not null then perform public.remove_board(p_rental, p_replace); end if;
  insert into public.rental_items (rental_id, board_id) values (p_rental, p_board);
end $$;
