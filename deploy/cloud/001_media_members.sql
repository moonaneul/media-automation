-- Run only in the church-media Supabase project's SQL Editor.
begin;
create table if not exists public.media_members (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('admin', 'editor')),
  active boolean not null default true,
  created_at timestamptz not null default now()
);
alter table public.media_members enable row level security;
revoke all on public.media_members from public, anon, authenticated;
grant select on public.media_members to authenticated;
drop policy if exists media_members_read_self on public.media_members;
create policy media_members_read_self on public.media_members
  for select to authenticated
  using (user_id = (select auth.uid()));

-- No client write policy: even admins cannot promote users through the public API.
-- Membership changes are performed by the project owner in SQL Editor for now.
insert into public.media_members (user_id, role, active)
values ('776e30f7-9dd3-4229-b9d4-23de72331f21', 'admin', true)
on conflict (user_id) do nothing;
commit;

select user_id, role, active from public.media_members
where user_id = '776e30f7-9dd3-4229-b9d4-23de72331f21';
