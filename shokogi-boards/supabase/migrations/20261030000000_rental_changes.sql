-- One rental's change trail, oldest first, for the owner's rental window and History (owner's request): the rental
-- itself, its board hand-outs, and edits to its customer while it ran. Runs as the caller, so only the owner gets
-- rows (the audit log is owner-only).
create function public.rental_changes(p_rental uuid)
returns setof public.audit_log language sql stable set search_path = '' as $$
  select a.* from public.audit_log a join public.rentals r on r.id = p_rental
  where (a.entity = 'rentals' and a.entity_id = r.id::text)
     or (a.entity = 'rental_items' and a.entity_id in (select i.id::text from public.rental_items i where i.rental_id = r.id))
     or (a.entity = 'customers' and a.action = 'update' and a.entity_id = r.customer_id::text
         and a.at between r.starts_at and coalesce(r.ended_at, now()))
  order by a.at, a.id
$$;
revoke execute on function public.rental_changes from public, anon;
grant execute on function public.rental_changes to authenticated;
