-- Bloowatch every minute. Bloowatch has no webhooks and no "changed since" filter, so a booking can only be noticed
-- by asking, and a cancellation only by a booking no longer coming back. Every minute is as live as it can be: a
-- hire entered in Bloowatch is a rental on the desk screen within the minute.
--
-- The timer calls the app over HTTP rather than doing the work in SQL, because the work is signing in to Bloowatch
-- and reading fifteen days of hires -- `app/api/bloowatch/sync/route.ts`, guarded by CRON_SECRET, exactly as the
-- Google Sheets timer is.
--
-- Two settings this expects, set per project (they hold the app's address and the shared secret, so they are not
-- written into a migration that lives in a public repository):
--   select set_config('app.base_url',    'https://shokogi-boards.vercel.app', false);
--   select set_config('app.cron_secret', '<the CRON_SECRET from Vercel>',     false);
-- In Supabase these go in the project's custom settings (Database > Settings), not here.

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Replacing rather than adding: re-running this migration must not leave two timers calling the same endpoint.
select cron.unschedule('bloowatch-sync') where exists (select 1 from cron.job where jobname = 'bloowatch-sync');

select cron.schedule('bloowatch-sync', '* * * * *', $$
  select net.http_post(
    url     := current_setting('app.base_url') || '/api/bloowatch/sync',
    headers := jsonb_build_object(
                 'Content-Type',  'application/json',
                 'Authorization', 'Bearer ' || current_setting('app.cron_secret')),
    body    := '{}'::jsonb,
    timeout_milliseconds := 55000   -- under the minute, so a slow run cannot overlap the next one
  );
$$);

-- What the sidebar shows: when it last ran, and what went wrong if anything. The Bloowatch login itself is not here
-- -- it goes in private_settings, which only the server's full-access key can read.
insert into public.app_settings (key, value)
values ('bloowatch_status', '{"at": null, "error": null}'::jsonb)
on conflict (key) do nothing;
