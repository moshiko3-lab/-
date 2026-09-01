-- WhatsApp: the school's own number, answered by the book itself.
--
-- Paste this whole file into the Supabase SQL editor and run it once, after
-- schema.sql. (Dashboard -> SQL Editor -> New query -> paste -> Run.)
-- Running it twice is safe.
--
-- What is here and what is deliberately not:
--
--   * The tables below hold the conversation, the contacts, the settings and
--     the queue of things waiting to be sent. Nothing else.
--   * The Meta access token is NOT here and must never be. It lives as a
--     secret on the Edge Function, which is the only thing that ever talks to
--     Meta. Anything in this database can be read by every device that signs
--     in; a token that can send messages as the school is not that.
--   * Sending never happens from a browser either. The page asks the function,
--     the function decides. That is what stops a signed-in phone from being
--     able to message anyone in the world as the school.
--
-- The shape follows the rest of the book: a table per thing, the record as
-- jsonb where it varies, row policies that let a member of the school see
-- their school and nothing else.

-- ------------------------------------------------------------- settings
-- One row for the school. What the automations do, when, and to whom -- the
-- app writes this from the WhatsApp screen, the function reads it.
create table if not exists public.wa_config (
  school     text primary key,
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- ------------------------------------------------------------- contacts
-- One row per number the school has ever spoken to. `last_in` is the whole
-- reason this table exists: WhatsApp only allows a free-form reply within 24
-- hours of the customer's own last message, and outside that window nothing
-- but an approved template will go. The app greys out the box rather than
-- letting somebody type a reply that Meta will refuse.
create table if not exists public.wa_contacts (
  school     text not null,
  wa_id      text not null,                     -- digits, no + and no spaces
  name       text,
  client_id  text,                              -- the client this is, if known
  staff_id   text,                              -- or the instructor
  opted_out  boolean not null default false,    -- said STOP: never write again
  needs_human boolean not null default false,   -- the bot stood down
  bot_until  timestamptz,                       -- ...until this passes
  last_in    timestamptz,
  last_out   timestamptz,
  unread     integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (school, wa_id)
);

-- ------------------------------------------------------------- messages
-- Every message either way, inbound and outbound, with the id Meta gave it so
-- a delivery report can find its message again.
create table if not exists public.wa_messages (
  id         text primary key,
  school     text not null,
  wa_id      text not null,
  direction  text not null,               -- 'in' | 'out'
  kind       text not null default 'text',
  body       text,
  template   text,
  status     text,                        -- queued|sent|delivered|read|failed
  error      text,
  raw        jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists wa_messages_thread
  on public.wa_messages (school, wa_id, created_at desc);
create index if not exists wa_messages_recent
  on public.wa_messages (school, created_at desc);

-- --------------------------------------------------------------- queue
-- Nothing is sent the moment it is worked out. A reminder due tomorrow is
-- written here today, and the tick sends it when it is due.
--
-- `dedupe` is the safeguard that matters: it is unique, so the same reminder
-- for the same person for the same session cannot be queued twice however
-- many times the planner runs. A tick that runs every five minutes would
-- otherwise message a customer every five minutes, which is the one failure
-- mode of this whole feature that a customer would actually feel.
create table if not exists public.wa_jobs (
  id         bigserial primary key,
  school     text not null,
  dedupe     text not null,
  wa_id      text not null,
  kind       text not null,               -- reminder | brief | manual
  payload    jsonb not null default '{}'::jsonb,
  run_after  timestamptz not null default now(),
  state      text not null default 'queued',   -- queued|sent|failed|skipped
  attempts   integer not null default 0,
  error      text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (school, dedupe)
);
create index if not exists wa_jobs_due
  on public.wa_jobs (school, state, run_after);

-- ------------------------------------------------------- clock and policies
do $$
declare t text;
        tables text[] := array['wa_config','wa_contacts','wa_messages','wa_jobs'];
begin
  foreach t in array tables loop
    execute format('alter table public.%I enable row level security', t);

    execute format('drop trigger if exists %I on public.%I', t || '_touch', t);
    execute format($f$
      create trigger %I before insert or update on public.%I
      for each row execute function public.touch_updated_at()$f$,
      t || '_touch', t);

    -- a member of the school reads and writes their school's rows. The
    -- function does not come through here at all: it holds the service key,
    -- which is not subject to these.
    execute format('drop policy if exists %I on public.%I', t || '_mine', t);
    execute format($f$
      create policy %I on public.%I
        for all to authenticated
        using (school = public.my_school())
        with check (school = public.my_school())$f$, t || '_mine', t);

    -- say it out loud when a message arrives, the same way the book does
    begin
      execute format('alter publication supabase_realtime add table public.%I', t);
    exception
      when duplicate_object then null;
      when undefined_object then null;
    end;
    execute format('alter table public.%I replica identity full', t);
  end loop;
end $$;

-- ------------------------------------------------------ the starting settings
-- Everything off. Nothing here messages a single customer until somebody turns
-- it on from the WhatsApp screen, which is the right default for a thing that
-- writes to the school's clients in the school's name.
insert into public.wa_config (school, data) values ('shokogi', jsonb_build_object(
  'tz',            'America/Panama',
  'bookingUrl',    'https://shokogimanager.com/book.html',
  'reminders',     jsonb_build_object(
      'on', false, 'hoursBefore', 18, 'template', 'session_reminder',
      'lang', 'en', 'quietFrom', 21, 'quietTo', 7),
  'brief',         jsonb_build_object(
      'on', false, 'at', '07:00', 'days', jsonb_build_array(0,1,2,3,4,5,6),
      'to', jsonb_build_array(), 'template', 'daily_brief', 'lang', 'en'),
  'bot',           jsonb_build_object(
      'on', false, 'hours', 'We are on the water 8:00-17:00 every day.',
      'greeting', 'Shokogi Surf School here. Ask me about lessons, prices or times, or say HUMAN and someone will answer.',
      'handover', 'Someone from the school will come back to you shortly.',
      'rules', jsonb_build_array())
)) on conflict (school) do nothing;

-- ---------------------------------------------------------------- the tick
-- Reminders and the morning brief need something to wake them up. pg_cron
-- calls the function on a schedule; pg_net does the calling.
--
-- Both extensions are one click each in Database -> Extensions (pg_cron,
-- pg_net). Then fill the two placeholders in and run this block. The secret is
-- whatever you set as WA_TICK_SECRET on the function -- it is what stops the
-- open internet from being able to make the school send its messages.
--
-- create extension if not exists pg_cron;
-- create extension if not exists pg_net;
--
-- select cron.schedule('whatsapp-tick', '*/5 * * * *', $cron$
--   select net.http_post(
--     url     := 'https://<PROJECT>.supabase.co/functions/v1/whatsapp/tick',
--     headers := jsonb_build_object('Content-Type','application/json',
--                                   'x-wa-secret','<WA_TICK_SECRET>'),
--     body    := '{}'::jsonb) $cron$);
--
-- To stop it again:  select cron.unschedule('whatsapp-tick');
-- What it has done:  select * from cron.job_run_details order by start_time desc limit 20;

-- ------------------------------------------------------------------ a check
-- After the function is deployed and the number connected, these three say
-- whether it is working:
--
--   select data from public.wa_config where school = 'shokogi';
--   select wa_id, direction, status, left(body, 60), created_at
--     from public.wa_messages order by created_at desc limit 20;
--   select kind, state, run_after, error from public.wa_jobs
--    order by created_at desc limit 20;
