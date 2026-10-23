-- Nightly backups (SPEC 9) and the Bloowatch booking webhook (SPEC 7.12).

-- Backups: a JSON snapshot of the data every night in a PRIVATE bucket (only the server's full-access key can
-- read or write it; no policies for anyone else). The app keeps the last 30.
insert into storage.buckets (id, name, public) values ('backups', 'backups', false) on conflict (id) do nothing;

-- The webhook matches customers exactly like the rentals screen does.
grant execute on function public.upsert_customer to service_role;
