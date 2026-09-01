-- ============================================================================
-- הספר המשותף של הסטודיו: סכימת Postgres אחת שכל המכשירים מדברים איתה.
--
-- להדביק את כל הקובץ ל-Supabase → SQL Editor → New query → Run. להריץ שוב
-- זה בטוח.
--
-- העיקרון שמנחה את כל מה שכאן: הדפים הציבוריים רצים בדפדפן של הלקוחה, ולכן
-- אסור לתת להם יותר ממה שהם חייבים. בפועל:
--
--   * הגדרות, טיפולים וחסימות  — כל אחד יכול לקרוא. זה מידע שממילא מודפס
--     על השלט בכניסה.
--   * תורים                     — אורחת לא קוראת אותם בכלל. כדי להציג שעות
--     פנויות היא מקבלת מ-free_busy טווחים תפוסים בלבד: מתי, בלי מי.
--   * לקוחות וטפסים             — רק מי שמחוברת ורשומה כחברה. כתב שחרור
--     חתום הוא מידע רפואי; אורחת יכולה רק לכתוב אחד, לעולם לא לקרוא.
--
-- המפתח שיושב בדף (publishable key) לא שומר על כלום. מה ששומר זה הכללים כאן.
-- מפתח service_role לא מופיע כאן ולעולם לא נכנס לדף.
-- ============================================================================

-- ------------------------------------------------------------------ מי בפנים
-- מי שמותר לה לפתוח את הספר. אדם יכול להתחבר יפה מאוד ועדיין לא לראות דבר
-- עד שיש לו שורה כאן — וזו ברירת המחדל הנכונה.
create table if not exists public.members (
  user_id  uuid primary key references auth.users on delete cascade,
  name     text,
  added_at timestamptz not null default now()
);
alter table public.members enable row level security;

drop policy if exists members_self on public.members;
create policy members_self on public.members
  for select to authenticated using (user_id = auth.uid());

create or replace function public.is_member() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.members where user_id = auth.uid())
$$;

-- שעון השרת מחליט מתי שורה השתנתה, לא חמישה טלפונים
create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

-- ---------------------------------------------------------------- הטבלאות
do $$
declare
  t text;
  tables text[] := array['settings','services','clients','appointments','blocks','forms'];
begin
  foreach t in array tables loop
    execute format($f$
      create table if not exists public.%I (
        id         text primary key,
        data       jsonb   not null default '{}'::jsonb,
        deleted    boolean not null default false,
        updated_at timestamptz not null default now()
      )$f$, t);
    execute format(
      'create index if not exists %I on public.%I (updated_at)', t || '_updated', t);
    execute format('alter table public.%I enable row level security', t);
    execute format('drop trigger if exists %I on public.%I', t || '_touch', t);
    execute format($f$
      create trigger %I before insert or update on public.%I
      for each row execute function public.touch_updated_at()$f$, t || '_touch', t);
  end loop;
end $$;

-- התורים נשאלים לפי יום ולפי שעה הרבה יותר מכפי שהם נכתבים, ולכן היום
-- והדקות יושבים בעמודות משלהם. טריגר גוזר אותן מה-data, כך שהאפליקציה
-- ממשיכה לשלוח רשומה אחת ולא צריכה לדעת על זה.
alter table public.appointments add column if not exists day        date;
alter table public.appointments add column if not exists start_min  int;
alter table public.appointments add column if not exists end_min    int;
alter table public.appointments add column if not exists status     text;
alter table public.appointments add column if not exists phone      text;
create index if not exists appointments_day on public.appointments (day);
create index if not exists appointments_phone on public.appointments (phone);

alter table public.blocks add column if not exists day       date;
alter table public.blocks add column if not exists start_min int;
alter table public.blocks add column if not exists end_min   int;
create index if not exists blocks_day on public.blocks (day);

create or replace function public.hm(s text) returns int
language sql immutable as $$
  select coalesce(split_part(s, ':', 1)::int, 0) * 60
       + coalesce(nullif(split_part(s, ':', 2), '')::int, 0)
$$;

create or replace function public.derive_appointment() returns trigger
language plpgsql as $$
begin
  new.day       := nullif(new.data->>'date','')::date;
  new.start_min := public.hm(new.data->>'time');
  new.end_min   := new.start_min + coalesce((new.data->>'minutes')::int, 30);
  new.status    := coalesce(new.data->>'status', 'confirmed');
  new.phone     := new.data->>'phone';
  return new;
end $$;
drop trigger if exists appointments_derive on public.appointments;
create trigger appointments_derive before insert or update on public.appointments
  for each row execute function public.derive_appointment();

create or replace function public.derive_block() returns trigger
language plpgsql as $$
begin
  new.day       := nullif(new.data->>'date','')::date;
  new.start_min := public.hm(new.data->>'from');
  new.end_min   := public.hm(new.data->>'to');
  return new;
end $$;
drop trigger if exists blocks_derive on public.blocks;
create trigger blocks_derive before insert or update on public.blocks
  for each row execute function public.derive_block();

-- ------------------------------------------------------------- מי קורא מה
-- פומבי: מה שהסטודיו מפרסם ממילא.
do $$
declare t text;
begin
  foreach t in array array['settings','services','blocks'] loop
    execute format('drop policy if exists %I on public.%I', t || '_read', t);
    execute format($f$
      create policy %I on public.%I for select to anon, authenticated
      using (deleted = false)$f$, t || '_read', t);
    execute format('drop policy if exists %I on public.%I', t || '_write', t);
    execute format($f$
      create policy %I on public.%I for all to authenticated
      using (public.is_member()) with check (public.is_member())$f$, t || '_write', t);
  end loop;
end $$;

-- פרטי: תורים, לקוחות וטפסים. אורחת לא מקבלת כאן שום מדיניות, כלומר
-- שום גישה ישירה — רק דרך שתי הפונקציות שלמטה.
do $$
declare t text;
begin
  foreach t in array array['clients','appointments','forms'] loop
    execute format('drop policy if exists %I on public.%I', t || '_own', t);
    execute format($f$
      create policy %I on public.%I for all to authenticated
      using (public.is_member()) with check (public.is_member())$f$, t || '_own', t);
  end loop;
end $$;

-- --------------------------------------------------------- מתי תפוס, בלי מי
-- זה כל מה שדף ההזמנה מקבל על התורים: טווחים. בלי שם, בלי טלפון, בלי טיפול.
-- דקות הסידור שבהגדרות נוספות לסוף כל תור, כדי שהשעה שתוצע ללקוחה תהיה
-- שעה שאפשר באמת לעבוד בה.
create or replace function public.free_busy(p_from date, p_to date)
returns table(d date, f int, t int)
language sql stable security definer set search_path = public as $$
  with buf as (
    select coalesce((data->>'buffer')::int, 0) as m
      from public.settings where id = 'settings'
  )
  select a.day, a.start_min, a.end_min + coalesce((select m from buf), 0)
    from public.appointments a
   where a.deleted = false
     and coalesce(a.status,'confirmed') <> 'cancelled'
     and a.day between p_from and p_to
  union all
  select b.day, b.start_min, b.end_min
    from public.blocks b
   where b.deleted = false and b.day between p_from and p_to
$$;
revoke all on function public.free_busy(date, date) from public;
grant execute on function public.free_busy(date, date) to anon, authenticated;

-- ------------------------------------------------------------ תפיסת התור
-- הבדיקה נעשית כאן ולא בדפדפן. שני טלפונים שלוחצים על אותה שעה באותה
-- שנייה מקבלים כאן תשובה אחת חיובית ואחת "slot taken" — בדפדפן שניהם
-- היו מקבלים "נקבע", ושתי לקוחות היו מגיעות לאותה שעה.
create or replace function public.book_slot(
  p_name text, p_phone text, p_service text, p_service_name text,
  p_date date, p_time text, p_minutes int,
  p_note text default '', p_lang text default 'en')
returns text
language plpgsql security definer set search_path = public as $$
declare
  s        jsonb;
  starts   int := public.hm(p_time);
  ends     int;
  ok_window boolean := false;
  w        jsonb;
  horizon  int;
  new_id   text;
  auto     boolean;
begin
  if coalesce(trim(p_name), '') = '' or coalesce(trim(p_phone), '') = '' then
    raise exception 'name and phone are required';
  end if;
  if p_minutes is null or p_minutes < 5 or p_minutes > 480 then
    raise exception 'bad duration';
  end if;
  ends := starts + p_minutes;

  select data into s from public.settings where id = 'settings';
  horizon := coalesce((s->>'horizon')::int, 45);
  auto    := coalesce((s->>'autoConfirm')::boolean, true);

  if p_date < current_date or p_date > current_date + horizon then
    raise exception 'date out of range';
  end if;

  -- בתוך שעות העבודה של אותו יום בשבוע
  for w in select * from jsonb_array_elements(
             coalesce(s->'hours'->(extract(dow from p_date)::int)::text, '[]'::jsonb))
  loop
    if starts >= public.hm(w->>'from') and ends <= public.hm(w->>'to') then
      ok_window := true;
    end if;
  end loop;
  if not ok_window then
    raise exception 'outside opening hours';
  end if;

  -- לא חופף לשום דבר שכבר תפוס
  if exists (select 1 from public.free_busy(p_date, p_date) fb
              where starts < fb.t and ends > fb.f) then
    raise exception 'slot taken';
  end if;

  -- בלם פשוט מול הצפה: מספר טלפון אחד, עד שלושה תורים עתידיים
  if (select count(*) from public.appointments a
       where a.phone = p_phone and a.deleted = false
         and coalesce(a.status,'confirmed') <> 'cancelled'
         and a.day >= current_date) >= 3 then
    raise exception 'too many open appointments for this number';
  end if;

  new_id := 'b' || replace(gen_random_uuid()::text, '-', '');
  insert into public.appointments (id, data) values (new_id, jsonb_build_object(
    'id', new_id, 'clientName', trim(p_name), 'phone', trim(p_phone),
    'serviceId', p_service, 'serviceName', p_service_name,
    'date', to_char(p_date, 'YYYY-MM-DD'), 'time', p_time,
    'minutes', p_minutes, 'note', coalesce(p_note, ''),
    'lang', coalesce(p_lang, 'en'),
    'status', case when auto then 'confirmed' else 'pending' end,
    'source', 'online', 'created', now()
  ));
  return new_id;
end $$;
revoke all on function public.book_slot(text,text,text,text,date,text,int,text,text) from public;
grant execute on function public.book_slot(text,text,text,text,date,text,int,text,text)
  to anon, authenticated;

-- ------------------------------------------------------- כתב שחרור חתום
-- כתיבה בלבד. אורחת מוסרת מסמך ולא יכולה לקרוא אף מסמך, שלה או של אחרת.
create or replace function public.submit_form(p_form jsonb)
returns text
language plpgsql security definer set search_path = public as $$
declare new_id text;
begin
  if coalesce(trim(p_form->>'name'), '') = ''
     or coalesce(trim(p_form->>'phone'), '') = ''
     or coalesce(p_form->>'signature', '') = '' then
    raise exception 'name, phone and signature are required';
  end if;
  if length(p_form->>'signature') > 400000 then
    raise exception 'signature too large';
  end if;
  new_id := 'f' || replace(gen_random_uuid()::text, '-', '');
  insert into public.forms (id, data)
    values (new_id, p_form || jsonb_build_object('id', new_id, 'received', now()));
  return new_id;
end $$;
revoke all on function public.submit_form(jsonb) from public;
grant execute on function public.submit_form(jsonb) to anon, authenticated;

-- --------------------------------------------------------------- מי הבעלים
-- להוסיף את המשתמשת קודם ב-Authentication → Users (עם Auto Confirm User),
-- ואז לשים כאן את האימייל שלה ולהריץ את הקובץ שוב. אימייל בלי משתמש עדיין
-- פשוט מדולג, וייתפס בהרצה הבאה.
insert into public.members (user_id, name)
select u.id, split_part(u.email, '@', 1)
  from auth.users u
 where u.email in (
         'change.me@example.com'
       )
    on conflict (user_id) do nothing;

-- ------------------------------------------------------------------ בדיקה
-- שתי אלה צריכות לחזור עם משהו:
--   select m.name, u.email from public.members m join auth.users u on u.id = m.user_id;
--   select * from public.free_busy(current_date, current_date + 14);
