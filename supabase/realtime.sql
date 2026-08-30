-- Instant updates, on their own.
--
-- schema.sql already does all of this -- this is the same thing on its own,
-- for a book that is already up and running and only needs the Live part
-- switched on. Paste it into Supabase → SQL Editor → New query → Run.
-- Running it more than once is safe.
--
-- What it does, in order: make sure Postgres has somewhere to announce
-- changes, put every table of the book into it, and have each change carry
-- the whole row rather than just its id -- without that last part a device
-- cannot tell whether a change belongs to its school, so edits and deletions
-- are dropped and two screens quietly drift apart.

do $$
declare
  t text;
  tables text[] := array[
    'clients','staff','products','gear','bookings','sessions','trips',
    'docs','invoices','tickets','cash','pos','tides','timeoff','gearblocks'
  ];
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime')
  then
    create publication supabase_realtime;
  end if;

  foreach t in array tables loop
    begin
      execute format(
        'alter publication supabase_realtime add table public.%I', t);
    exception
      when duplicate_object then null;   -- already announced, nothing to do
    end;
    execute format('alter table public.%I replica identity full', t);
  end loop;
end $$;

-- The check. This should come back with all fifteen table names; if it comes
-- back empty, nothing above took and the app will stay on its fifteen-second
-- fallback.
select tablename
  from pg_publication_tables
 where pubname = 'supabase_realtime'
 order by tablename;
