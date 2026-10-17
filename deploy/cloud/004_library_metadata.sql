begin;
create table if not exists public.media_songs (
 id text primary key, payload jsonb not null check(jsonb_typeof(payload)='object')
);
create table if not exists public.media_files (
 digest text primary key check(digest ~ '^[a-f0-9]{64}$'),
 filename text not null, size bigint not null check(size>0),
 drive_id text not null, item_id text not null,
 item jsonb not null check(jsonb_typeof(item)='object')
);
create table if not exists public.media_song_assets (
 song_id text not null references public.media_songs(id),
 digest text not null references public.media_files(digest), filename text not null,
 primary key(song_id,digest)
);
create table if not exists public.media_asset_reviews (
 song_id text not null, digest text not null, payload jsonb not null,
 primary key(song_id,digest), foreign key(song_id,digest) references public.media_song_assets(song_id,digest)
);
create table if not exists public.media_attachments (
 day date not null, service text not null check(service in ('wednesday','friday','sunday')),
 slot text not null, filename text not null, digest text not null references public.media_files(digest),
 primary key(day,service,slot)
);
create table if not exists public.media_bulletin_settings (
 id integer primary key check(id=1), revision bigint not null check(revision>=0),
 payload jsonb not null check(jsonb_typeof(payload)='object')
);
create table if not exists public.media_archives (
 file_id text primary key, day date not null,
 service text not null check(service in ('wednesday','friday','sunday')),
 kind text not null check(kind in ('ppt','pdf')), item jsonb not null
);
do $$
declare v_table text;
begin
 foreach v_table in array array['media_songs','media_files','media_song_assets','media_asset_reviews',
   'media_attachments','media_bulletin_settings','media_archives'] loop
  execute format('alter table public.%I enable row level security',v_table);
  execute format('revoke all on public.%I from public,anon,authenticated',v_table);
  execute format('grant select on public.%I to authenticated',v_table);
  execute format('drop policy if exists media_team_read on public.%I',v_table);
  execute format('create policy media_team_read on public.%I for select to authenticated using
   (exists(select 1 from public.media_members m where m.user_id=(select auth.uid()) and m.active))',v_table);
 end loop;
end;
$$;
commit;
