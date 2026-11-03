-- Apply only in a separately selected database project for 4LEAF.
-- No browser user may read/write chat archives through Supabase Data API.
create table if not exists public.fourleaf_chat_snapshots (
  slot text primary key check (slot ~ '^[a-z0-9_-]{1,48}$'),
  revision bigint not null check (revision >= 1),
  payload text not null,
  sha256 text not null check (sha256 ~ '^[a-f0-9]{64}$'),
  updated_at timestamptz not null default now()
);
alter table public.fourleaf_chat_snapshots enable row level security;
revoke all on table public.fourleaf_chat_snapshots from anon, authenticated;
grant select, insert, update on public.fourleaf_chat_snapshots to service_role;
comment on table public.fourleaf_chat_snapshots is
 '4LEAF encrypted and checksum-verified chat snapshots with revision CAS, no browser access';
