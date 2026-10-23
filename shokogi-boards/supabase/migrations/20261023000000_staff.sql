-- Staff accounts (SPEC 3, 7.9): the login shown in Settings, a temporary password that must be changed on
-- first login, and at least one active owner at all times.

alter table public.profiles add column login text not null default '';
alter table public.profiles add column must_change_password boolean not null default false;

-- Staff log in with a username, stored by Auth as <username>@staff.shokogi.invalid (lib/login.ts).
create function public.login_of(email text) returns text language sql immutable set search_path = '' as $$
  select regexp_replace(coalesce(email, ''), '@staff\.shokogi\.invalid$', '')
$$;

update public.profiles p set login = public.login_of(u.email) from auth.users u where u.id = p.id;

create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, name, login)
  values (new.id, coalesce(nullif(new.raw_user_meta_data->>'name', ''), split_part(new.email, '@', 1)), public.login_of(new.email));
  return new;
end $$;

-- Nobody can demote or deactivate the last active owner (including themselves).
create function public.profiles_keep_owner() returns trigger
language plpgsql set search_path = '' as $$
begin
  if not exists (select 1 from public.profiles where role = 'owner' and active) then
    raise exception 'Keep at least one active owner.';
  end if;
  return null;
end $$;
create trigger profiles_keep_owner after update or delete on public.profiles
  for each statement execute function public.profiles_keep_owner();

-- Called by a signed-in person right after choosing their own password.
create function public.password_changed() returns void
language sql security definer set search_path = '' as $$
  update public.profiles set must_change_password = false where id = auth.uid()
$$;
revoke execute on function public.password_changed from public, anon;
grant execute on function public.password_changed to authenticated;
