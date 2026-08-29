-- The shared book: one Postgres schema for every device the school opens.
--
-- Paste this whole file into the Supabase SQL editor and run it once.
-- (Dashboard → SQL Editor → New query → paste → Run.)
--
-- The shape is deliberately dull: a table per collection, each row carrying
-- the record as jsonb. Rows rather than one big document, so the counter
-- taking a booking and an instructor moving a session at the same moment do
-- not overwrite each other; jsonb rather than columns, so the app can grow a
-- field without a migration on a Saturday.
--
-- Nothing here trusts the browser. The publishable key in the page can do
-- exactly what these policies allow and no more: read and write the rows of
-- the school you are a member of, once you have signed in.

-- ---------------------------------------------------------------- members
-- Who may see which school's book. A person with no row here can sign in and
-- still see nothing, which is the right default.
create table if not exists public.members (
  user_id uuid primary key references auth.users on delete cascade,
  school  text not null,
  name    text,
  added_at timestamptz not null default now()
);
alter table public.members enable row level security;

drop policy if exists members_self on public.members;
create policy members_self on public.members
  for select to authenticated
  using (user_id = auth.uid());

-- the school this signed-in person belongs to
create or replace function public.my_school() returns text
language sql stable security definer set search_path = public as $$
  select school from public.members where user_id = auth.uid()
$$;

-- the server's clock decides when a row changed, not fifteen laptops
create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

-- ------------------------------------------------------------ the tables
do $$
declare
  t text;
  tables text[] := array[
    'clients','staff','products','gear','bookings','sessions','trips',
    'docs','invoices','tickets','cash','pos','tides','timeoff','gearblocks'
  ];
begin
  foreach t in array tables loop
    execute format($f$
      create table if not exists public.%I (
        id         text primary key,
        school     text not null,
        deleted    boolean not null default false,
        data       jsonb   not null default '{}'::jsonb,
        updated_at timestamptz not null default now()
      )$f$, t);

    -- what a pull asks for: this school, changed since last time
    execute format(
      'create index if not exists %I on public.%I (school, updated_at)',
      t || '_school_updated', t);

    execute format('alter table public.%I enable row level security', t);

    execute format('drop trigger if exists %I on public.%I',
                   t || '_touch', t);
    execute format($f$
      create trigger %I before insert or update on public.%I
      for each row execute function public.touch_updated_at()$f$,
      t || '_touch', t);

    -- one policy, both directions: your school's rows, signed in, and every
    -- row you write has to carry your school too
    execute format('drop policy if exists %I on public.%I', t || '_mine', t);
    execute format($f$
      create policy %I on public.%I
        for all to authenticated
        using (school = public.my_school())
        with check (school = public.my_school())$f$, t || '_mine', t);
  end loop;
end $$;

-- --------------------------------------------------------------- the crew
-- Add each person in Authentication → Users, then give them the school here.
-- Until a person has a row in members they see an empty book.
--
--   insert into public.members (user_id, school, name)
--   select id, 'shokogi', 'Moshe' from auth.users where email = 'you@example.com'
--   on conflict (user_id) do update set school = excluded.school;

-- ------------------------------------------------------------- a check
-- After signing in from the app, this should return 'shokogi':
--   select public.my_school();
