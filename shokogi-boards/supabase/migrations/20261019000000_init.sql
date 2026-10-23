-- Shokogi Boards: schema, permissions (RLS), defaults. See SPEC.md sections 3 and 4.

-- ---------- Tables ----------

create table public.profiles (
  id uuid primary key references auth.users on delete cascade,
  name text not null default '',
  role text not null default 'staff' check (role in ('owner', 'staff')),
  active boolean not null default false, -- a new login gets no access until the owner activates it
  created_at timestamptz not null default now()
);

create table public.board_types (
  id uuid primary key default gen_random_uuid(),
  name text not null check (btrim(name) <> ''),
  sort_order int not null default 0,
  is_system boolean not null default false, -- true only for "Other"
  check (is_system or lower(btrim(name)) <> 'other')
);
create unique index board_types_name_key on public.board_types (lower(btrim(name)));
create unique index board_types_one_system on public.board_types (is_system) where is_system;

create table public.boards (
  id uuid primary key default gen_random_uuid(),
  name text not null check (btrim(name) <> ''),
  type_id uuid not null references public.board_types,
  notes text not null default '',
  in_repair boolean not null default false,
  photo_path text,
  thumb_path text,
  source_file_name text, -- original photo file name, for re-import matching
  created_at timestamptz not null default now(),
  deleted_at timestamptz -- soft delete keeps history working
);
create unique index boards_source_file_key on public.boards (source_file_name) where source_file_name is not null and deleted_at is null;

create table public.customers (
  id uuid primary key default gen_random_uuid(),
  name text not null check (btrim(name) <> ''),
  phone text not null default '',
  phone_digits text generated always as (regexp_replace(phone, '\D', '', 'g')) stored,
  email text not null default '',
  notes text not null default '',
  created_at timestamptz not null default now()
);
create unique index customers_phone_digits_key on public.customers (phone_digits) where phone_digits <> '';
create index customers_name_idx on public.customers (lower(btrim(name)));

create table public.rental_lengths (
  id uuid primary key default gen_random_uuid(),
  label text not null check (btrim(label) <> ''),
  minutes int not null check (minutes > 0)
);

create table public.rentals (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers,
  starts_at timestamptz not null default now(),
  due_at timestamptz not null,
  ended_at timestamptz, -- null = active
  source text not null default 'manual' check (source in ('manual', 'bloowatch')),
  bloowatch_booking_id text unique,
  notes text not null default '',
  created_by uuid references public.profiles default auth.uid(),
  ended_by uuid references public.profiles,
  created_at timestamptz not null default now()
);
create index rentals_active_idx on public.rentals (due_at) where ended_at is null;
create index rentals_customer_idx on public.rentals (customer_id);
create index rentals_starts_idx on public.rentals (starts_at);

create table public.rental_items (
  id uuid primary key default gen_random_uuid(),
  rental_id uuid not null references public.rentals on delete cascade,
  board_id uuid not null references public.boards,
  assigned_at timestamptz not null default now(),
  unassigned_at timestamptz, -- null = the board is with the customer now
  assigned_by uuid references public.profiles default auth.uid(),
  unassigned_by uuid references public.profiles
);
-- Two devices can never hand out the same board.
create unique index rental_items_one_current_per_board on public.rental_items (board_id) where unassigned_at is null;
create index rental_items_rental_idx on public.rental_items (rental_id);

create table public.audit_log (
  id bigint generated always as identity primary key,
  actor_id uuid, -- no FK: the log outlives everything
  action text not null,
  entity text not null,
  entity_id text,
  details jsonb,
  at timestamptz not null default now()
);
create index audit_log_entity_idx on public.audit_log (entity, entity_id);

create table public.app_settings (
  key text primary key,
  value jsonb not null
);

-- ---------- Defaults ----------

insert into public.board_types (name, sort_order, is_system) values
  ('Softboard', 1, false), ('Longboard', 2, false), ('Midlength', 3, false),
  ('Funboard', 4, false), ('Shortboard', 5, false), ('Other', 1000, true);

insert into public.rental_lengths (label, minutes) values
  ('1 hour', 60), ('2 hours', 120), ('3 hours', 180), ('Half day (4 hours)', 240),
  ('1 day', 1440), ('2 days', 2880), ('3 days', 4320), ('1 week', 10080);

insert into public.app_settings (key, value) values
  ('sheets_enabled', 'false'), ('bloowatch_enabled', 'false');

-- ---------- Who is asking ----------

create function public.is_member() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles where id = auth.uid() and active)
$$;

create function public.is_owner() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles where id = auth.uid() and active and role = 'owner')
$$;

-- Every new login gets an inactive staff profile; the owner (or the server, for accounts it creates) activates it.
create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, name)
  values (new.id, coalesce(nullif(new.raw_user_meta_data->>'name', ''), split_part(new.email, '@', 1)));
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------- Rules the database enforces ----------

-- Deleting a type moves its boards to Other.
create function public.board_types_before_delete() returns trigger
language plpgsql set search_path = '' as $$
begin
  update public.boards set type_id = (select id from public.board_types where is_system) where type_id = old.id;
  return old;
end $$;
create trigger board_types_before_delete before delete on public.board_types
  for each row execute function public.board_types_before_delete();

-- At least one rental length must exist.
create function public.rental_lengths_keep_one() returns trigger
language plpgsql set search_path = '' as $$
begin
  if not exists (select 1 from public.rental_lengths) then
    raise exception 'Keep at least one rental length.';
  end if;
  return null;
end $$;
create trigger rental_lengths_keep_one after delete on public.rental_lengths
  for each statement execute function public.rental_lengths_keep_one();

-- Only the owner deletes boards, and never a rented one. A rented board can't go to repair.
-- (auth.uid() is null for server-side scripts, which are trusted.)
create function public.boards_guard() returns trigger
language plpgsql set search_path = '' as $$
declare rented boolean := exists (select 1 from public.rental_items where board_id = new.id and unassigned_at is null);
begin
  if new.deleted_at is distinct from old.deleted_at then
    if auth.uid() is not null and not public.is_owner() then raise exception 'Only the owner can delete boards.'; end if;
    if new.deleted_at is not null and rented then raise exception 'This board is rented. Mark it returned first.'; end if;
  end if;
  if new.in_repair and not old.in_repair and rented then
    raise exception 'This board is rented. Mark it returned first.';
  end if;
  return new;
end $$;
create trigger boards_guard before update on public.boards
  for each row execute function public.boards_guard();

-- A board can only be handed out on an active rental, and only when it's in service.
-- (Past items, e.g. from the data import, are not checked.)
create function public.rental_items_guard() returns trigger
language plpgsql set search_path = '' as $$
begin
  if new.unassigned_at is not null then return new; end if;
  if exists (select 1 from public.boards where id = new.board_id and (deleted_at is not null or in_repair)) then
    raise exception 'This board is not available.';
  end if;
  if exists (select 1 from public.rentals where id = new.rental_id and ended_at is not null) then
    raise exception 'This rental has already ended.';
  end if;
  return new;
end $$;
create trigger rental_items_guard before insert on public.rental_items
  for each row execute function public.rental_items_guard();

-- ---------- Audit log: who changed what, before and after ----------

create function public.audit() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  o jsonb := case when tg_op <> 'INSERT' then to_jsonb(old) end;
  n jsonb := case when tg_op <> 'DELETE' then to_jsonb(new) end;
  before_ jsonb := o;
  after_ jsonb := n;
begin
  if tg_op = 'UPDATE' then -- keep only the fields that changed
    select jsonb_object_agg(key, o->key), jsonb_object_agg(key, value) into before_, after_
    from jsonb_each(n) where o->key is distinct from value;
    if after_ is null then return new; end if; -- nothing changed
  end if;
  insert into public.audit_log (actor_id, action, entity, entity_id, details)
  values (auth.uid(), lower(tg_op), tg_table_name,
          coalesce(n->>'id', o->>'id', n->>'key', o->>'key'),
          jsonb_build_object('before', before_, 'after', after_));
  return coalesce(new, old);
end $$;

do $$
declare t text;
begin
  foreach t in array array['profiles', 'board_types', 'boards', 'customers', 'rental_lengths', 'rentals', 'rental_items', 'app_settings'] loop
    execute format('create trigger audit after insert or update or delete on public.%I for each row execute function public.audit()', t);
  end loop;
end $$;

-- ---------- Permissions (Row Level Security) ----------
-- Staff and owner: everyday work. Owner only: settings, types, lengths, staff, audit log.

revoke all on all tables in schema public from anon, authenticated;

alter table public.profiles enable row level security;
alter table public.board_types enable row level security;
alter table public.boards enable row level security;
alter table public.customers enable row level security;
alter table public.rental_lengths enable row level security;
alter table public.rentals enable row level security;
alter table public.rental_items enable row level security;
alter table public.audit_log enable row level security;
alter table public.app_settings enable row level security;

grant select, update on public.profiles to authenticated;
create policy "read own profile, members read all" on public.profiles for select to authenticated using (id = auth.uid() or public.is_member());
create policy "owner edits profiles" on public.profiles for update to authenticated using (public.is_owner()) with check (public.is_owner());

grant select, insert, update, delete on public.board_types to authenticated;
create policy "members read types" on public.board_types for select to authenticated using (public.is_member());
create policy "owner adds types" on public.board_types for insert to authenticated with check (public.is_owner() and not is_system);
create policy "owner renames types" on public.board_types for update to authenticated using (public.is_owner() and not is_system) with check (not is_system);
create policy "owner removes types" on public.board_types for delete to authenticated using (public.is_owner() and not is_system);

grant select, insert, update, delete on public.rental_lengths to authenticated;
create policy "members read lengths" on public.rental_lengths for select to authenticated using (public.is_member());
create policy "owner adds lengths" on public.rental_lengths for insert to authenticated with check (public.is_owner());
create policy "owner edits lengths" on public.rental_lengths for update to authenticated using (public.is_owner());
create policy "owner removes lengths" on public.rental_lengths for delete to authenticated using (public.is_owner());

grant select, insert, update, delete on public.app_settings to authenticated;
create policy "members read settings" on public.app_settings for select to authenticated using (public.is_member());
create policy "owner writes settings" on public.app_settings for all to authenticated using (public.is_owner()) with check (public.is_owner());

-- Everyday tables: every active member reads and writes; nobody hard-deletes.
grant select, insert, update on public.boards, public.customers, public.rentals, public.rental_items to authenticated;
create policy "members read boards" on public.boards for select to authenticated using (public.is_member());
create policy "members add boards" on public.boards for insert to authenticated with check (public.is_member());
create policy "members edit boards" on public.boards for update to authenticated using (public.is_member());
create policy "members read customers" on public.customers for select to authenticated using (public.is_member());
create policy "members add customers" on public.customers for insert to authenticated with check (public.is_member());
create policy "members edit customers" on public.customers for update to authenticated using (public.is_member());
create policy "members read rentals" on public.rentals for select to authenticated using (public.is_member());
create policy "members add rentals" on public.rentals for insert to authenticated with check (public.is_member());
create policy "members edit rentals" on public.rentals for update to authenticated using (public.is_member());
create policy "members read items" on public.rental_items for select to authenticated using (public.is_member());
create policy "members add items" on public.rental_items for insert to authenticated with check (public.is_member());
create policy "members edit items" on public.rental_items for update to authenticated using (public.is_member());

grant select on public.audit_log to authenticated;
create policy "owner reads audit log" on public.audit_log for select to authenticated using (public.is_owner());

-- ---------- Board photos (public read: surfboard photos only, needed for =IMAGE() in Google Sheets) ----------

insert into storage.buckets (id, name, public) values ('boards', 'boards', true) on conflict (id) do nothing;
create policy "members read board photos" on storage.objects for select to authenticated using (bucket_id = 'boards' and public.is_member());
create policy "members upload board photos" on storage.objects for insert to authenticated with check (bucket_id = 'boards' and public.is_member());
create policy "members replace board photos" on storage.objects for update to authenticated using (bucket_id = 'boards' and public.is_member());
create policy "members remove board photos" on storage.objects for delete to authenticated using (bucket_id = 'boards' and public.is_member());

-- ---------- Live updates across devices ----------

alter publication supabase_realtime add table
  public.boards, public.board_types, public.customers, public.rental_lengths, public.rentals, public.rental_items, public.app_settings;
