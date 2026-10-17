begin;
create table if not exists public.media_connections (
 id text primary key check(id='onedrive'), revision bigint not null check(revision>0),
 ciphertext text not null, updated_at timestamptz not null default now()
);
alter table public.media_connections enable row level security;
revoke all on public.media_connections from public,anon,authenticated;
grant select,insert,update on public.media_connections to service_role;
-- No browser role or team member can read the ciphertext or write credentials.
commit;
