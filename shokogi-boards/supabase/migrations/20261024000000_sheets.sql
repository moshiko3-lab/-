-- Google Sheets mirror (SPEC 7.11), connected with "Sign in with Google" from Settings.
-- The Google connection (a refresh token) is a secret: it lives in private_settings, which only the server's
-- full-access key can read. What everyone may see (sheet link, connected account, last sync) is in app_settings.
create table public.private_settings (
  key text primary key,
  value jsonb not null
);
alter table public.private_settings enable row level security; -- no policies: nobody but the server
revoke all on public.private_settings from anon, authenticated;

-- The server reads the whole history for the sheet, and a database timer (pg_cron + pg_net, set up per project
-- with the app's address and a secret) asks it to sync every 10 minutes.
grant execute on function public.history_search to service_role;
create extension if not exists pg_cron;
create extension if not exists pg_net;
