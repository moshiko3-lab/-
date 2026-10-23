-- Per-board totals for cards and Board details: times rented, hours rented, last rented.
-- Counts finished hand-outs only (returned, or swapped out mid-rental), like the prototype's history.
-- security_invoker: the view obeys the caller's Row Level Security instead of bypassing it.
create view public.board_stats with (security_invoker = true) as
select board_id,
       count(*)::int as times_rented,
       round(extract(epoch from sum(unassigned_at - assigned_at)) / 3600)::int as hours_rented,
       max(assigned_at) as last_rented
from public.rental_items
where unassigned_at is not null
group by board_id;

grant select on public.board_stats to authenticated;
