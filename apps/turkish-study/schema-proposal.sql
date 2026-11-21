-- Schema proposal only. Apply ONLY to a new dedicated project. Not deployed.
begin;
create table public.study_profiles(
 user_id uuid primary key references auth.users(id) on delete cascade,
 course_version text not null,
 departure_date date,
 created_at timestamptz not null default now()
);
create table public.study_events(
 user_id uuid not null references auth.users(id) on delete cascade,
 event_id uuid not null,
 course_version text not null,
 kind text not null check(kind in ('lesson_completed','study_seconds','answer','review','conversation','self_assessment')),
 entity_id text not null,
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 client_at timestamptz not null,
 recorded_at timestamptz not null default now(),
 primary key(user_id,event_id)
);
create index study_events_user_time on public.study_events(user_id,recorded_at);
alter table public.study_profiles enable row level security;
alter table public.study_events enable row level security;
revoke all on public.study_profiles, public.study_events from anon, authenticated;
grant select,insert,update on public.study_profiles to authenticated;
grant select,insert on public.study_events to authenticated;
create policy profile_read on public.study_profiles for select to authenticated using ((select auth.uid())=user_id);
create policy profile_insert on public.study_profiles for insert to authenticated with check ((select auth.uid())=user_id);
create policy profile_update on public.study_profiles for update to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
create policy event_read on public.study_events for select to authenticated using ((select auth.uid())=user_id);
create policy event_insert on public.study_events for insert to authenticated with check ((select auth.uid())=user_id);
commit;
-- events are append-only: retry with same event_id using conflict-safe insert; server-derived projections planned.
-- Verify two authenticated accounts, unauthorized reads/inserts, anon deny, duplicate UUID and export/restore.
