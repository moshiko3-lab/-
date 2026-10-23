-- History (SPEC 7.8) and "Most rented boards" (7.1). Everything runs as the caller, so Row Level Security applies.

-- Returned rentals, one row each: who, the boards they brought back, who marked it returned, and a search text
-- (customer, phone, and every board used, swapped ones too).
create view public.rental_history with (security_invoker = true) as
select r.id, r.starts_at, r.due_at, r.ended_at,
       c.id as customer_id, c.name as customer, c.phone,
       p.name as ended_by,
       coalesce(jsonb_agg(jsonb_build_object('id', b.id, 'name', b.name, 'type', t.name) order by i.assigned_at)
                filter (where i.unassigned_at = r.ended_at), '[]') as boards, -- return_rental closes them at ended_at exactly
       lower(c.name || ' ' || c.phone || ' ' || c.phone_digits || ' ' || coalesce(string_agg(b.name, ' '), '')) as search
from public.rentals r
join public.customers c on c.id = r.customer_id
left join public.profiles p on p.id = r.ended_by
left join public.rental_items i on i.rental_id = r.id
left join public.boards b on b.id = i.board_id
left join public.board_types t on t.id = b.type_id
where r.ended_at is not null
group by r.id, c.id, p.name;

grant select on public.rental_history to authenticated;

-- One page of History plus the totals for the same filters, in one call. Dates filter on the start time,
-- p_to is exclusive. Every search word must appear (words come lower-cased, with LIKE wildcards escaped).
create function public.history_search(p_from timestamptz, p_to timestamptz, p_words text[], p_limit int default 300)
returns jsonb language sql stable set search_path = '' as $$
  with hit as (
    select * from public.rental_history h
    where (p_from is null or h.starts_at >= p_from) and (p_to is null or h.starts_at < p_to)
      and (select bool_and(h.search like '%' || w || '%') from unnest(coalesce(p_words, '{}')) w) is not false
  )
  select jsonb_build_object(
    'rentals', count(*),
    'hours', coalesce(round(extract(epoch from sum(ended_at - starts_at)) / 3600), 0),
    'average_minutes', coalesce(round(extract(epoch from avg(ended_at - starts_at)) / 60), 0),
    'late', count(*) filter (where ended_at > due_at),
    'rows', coalesce((select jsonb_agg(to_jsonb(x) - 'search' order by x.ended_at desc)
                      from (select * from hit order by ended_at desc limit p_limit) x), '[]'))
  from hit
$$;

-- The 5 boards in the fleet handed out most since p_since (finished hand-outs, like the History).
create function public.most_rented(p_since timestamptz)
returns table (board_id uuid, name text, thumb_path text, rentals int) language sql stable set search_path = '' as $$
  select b.id, b.name, b.thumb_path, count(*)::int
  from public.rental_items i join public.boards b on b.id = i.board_id
  where i.unassigned_at >= p_since and b.deleted_at is null
  group by b.id
  order by 4 desc, b.name
  limit 5
$$;

revoke execute on function public.history_search, public.most_rented from public, anon;
grant execute on function public.history_search, public.most_rented to authenticated;
