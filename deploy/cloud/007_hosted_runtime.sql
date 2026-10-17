begin;
create table if not exists public.media_sessions (
 id text primary key check(id ~ '^[a-f0-9]{64}$'),
 user_id uuid not null references auth.users(id), expires_at timestamptz not null,
 ciphertext text not null check(length(ciphertext) between 1 and 32768)
);
create index if not exists media_sessions_expiry on public.media_sessions(expires_at);
alter table public.media_sessions enable row level security;
revoke all on public.media_sessions from public,anon,authenticated;
grant select,insert,delete on public.media_sessions to service_role;
alter table public.media_jobs add column if not exists dispatch_at timestamptz;

create or replace function public.media_dispatch_job(p_id uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare v_id uuid;
begin
 update public.media_jobs j set dispatch_at=now() where id=p_id and status='queued'
  and dispatch_at is null and deadline>now()
  and exists(select 1 from public.media_members where user_id=j.queued_by and active)
  returning id into v_id;
 return jsonb_build_object('dispatch',v_id is not null);
end; $$;
revoke all on function public.media_dispatch_job(uuid) from public,anon,authenticated;
grant execute on function public.media_dispatch_job(uuid) to service_role;

create or replace function public.media_job_active(p_id uuid,p_execution text)
returns jsonb language sql stable security invoker set search_path='' as $$
 select jsonb_build_object('active',exists(select 1 from public.media_jobs j where j.id=p_id
  and j.status='running' and j.execution=p_execution and j.deadline>now()
  and exists(select 1 from public.media_members where user_id=j.queued_by and active)));
$$;
revoke all on function public.media_job_active(uuid,text) from public,anon,authenticated;
grant execute on function public.media_job_active(uuid,text) to service_role;

create or replace function public.media_cancel_job(p_id uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_id uuid;
begin
 if not exists(select 1 from public.media_members where user_id=auth.uid() and active and role in ('admin','editor')) then
  raise exception 'Active membership required' using errcode='42501'; end if;
 update public.media_jobs set status='failed',finished_at=now(),result='{"error":"제작이 취소되었습니다."}'
  where id=p_id and status in ('queued','running') and (queued_by=auth.uid() or exists(
   select 1 from public.media_members where user_id=auth.uid() and active and role='admin')) returning id into v_id;
 return jsonb_build_object('cancelled',v_id is not null);
end; $$;
revoke all on function public.media_cancel_job(uuid) from public,anon,authenticated;
grant execute on function public.media_cancel_job(uuid) to authenticated;

create table if not exists public.media_catalog_version(id integer primary key check(id=1),revision bigint not null);
insert into public.media_catalog_version values(1,1) on conflict do nothing;
alter table public.media_catalog_version enable row level security;
revoke all on public.media_catalog_version from public,anon,authenticated;
grant select on public.media_catalog_version to authenticated;
drop policy if exists media_catalog_version_read on public.media_catalog_version;
create policy media_catalog_version_read on public.media_catalog_version for select to authenticated using
 (exists(select 1 from public.media_members where user_id=auth.uid() and active));

create or replace function public.media_edit_catalog(p_revision bigint,p_operation text,p_body jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_revision bigint; v_data jsonb; v_song text; v_digest text; v_current bigint;
begin
 if not exists(select 1 from public.media_members where user_id=auth.uid() and active and role in ('admin','editor')) then
  raise exception 'Active membership required' using errcode='42501'; end if;
 if p_body is null or jsonb_typeof(p_body)<>'object' or octet_length(p_body::text)>12582912 then
  raise exception 'Invalid catalog request' using errcode='22023'; end if;
 select revision into v_revision from public.media_catalog_version where id=1 for update;
 if p_revision is null or p_revision<>v_revision then return jsonb_build_object('saved',false,'revision',v_revision); end if;
 v_song:=p_body->>'song_id'; v_digest:=p_body->>'digest';
 if p_operation='song' then
  v_data:=p_body->'song';
  if jsonb_typeof(v_data) is distinct from 'object' or jsonb_typeof(v_data->'title') is distinct from 'string' or length(trim(v_data->>'title')) not between 1 and 200
   or jsonb_typeof(v_data->'aliases') is distinct from 'array' or jsonb_array_length(v_data->'aliases')>20
   or (v_data->>'edition' is not null and v_data->>'edition' not in ('new','old'))
   or (v_data->>'edition' is not null and (v_data->>'number')::integer not between 1 and 999)
   or (v_data->>'edition' is null and v_data->>'number' is not null) then
   raise exception 'Invalid song' using errcode='22023'; end if;
  insert into public.media_songs values(v_data->>'id',v_data);
 elsif p_operation='review' then
  v_data:=p_body->'review';
  if jsonb_typeof(v_data->'technical') is distinct from 'boolean' or jsonb_typeof(v_data->'church') is distinct from 'boolean'
   or coalesce(v_data->>'permission','') not in ('unknown','allowed','not_allowed')
   or length(coalesce(v_data->>'note',''))>2000 then raise exception 'Invalid review' using errcode='22023'; end if;
  insert into public.media_asset_reviews values(v_song,v_digest,v_data) on conflict(song_id,digest) do update set payload=excluded.payload;
 elsif p_operation='attachment' then
  if p_body->>'service' not in ('wednesday','friday','sunday') or length(p_body->>'slot') not between 1 and 200
    then raise exception 'Invalid attachment' using errcode='22023'; end if;
  insert into public.media_attachments values((p_body->>'day')::date,p_body->>'service',p_body->>'slot',p_body->>'filename',v_digest)
   on conflict(day,service,slot) do update set filename=excluded.filename,digest=excluded.digest;
  if v_song is not null then insert into public.media_song_assets values(v_song,v_digest,p_body->>'filename') on conflict do nothing; end if;
 elsif p_operation='song_asset' then
  if p_body->>'replace_digest' is not null and p_body->>'replace_digest'<>v_digest then
   delete from public.media_asset_reviews where song_id=v_song and digest=p_body->>'replace_digest';
   delete from public.media_song_assets where song_id=v_song and digest=p_body->>'replace_digest';
  end if;
  insert into public.media_song_assets values(v_song,v_digest,p_body->>'filename') on conflict do nothing;
 elsif p_operation='remove' then
  if v_song is not null then
   delete from public.media_asset_reviews where song_id=v_song and digest=v_digest;
   delete from public.media_song_assets where song_id=v_song and digest=v_digest;
  else
   delete from public.media_attachments where day=(p_body->>'date')::date and service=p_body->>'service' and slot=p_body->>'slot' and digest=v_digest;
  end if;
 elsif p_operation='settings' then
  select revision into v_current from public.media_bulletin_settings where id=1;
  if coalesce(v_current,0) is distinct from (p_body->>'revision')::bigint then
   return jsonb_build_object('saved',false,'revision',v_revision); end if;
  v_data:=p_body->'data';
  if jsonb_typeof(v_data)<>'object' or (v_data->>'reference_year')::integer not between 2000 and 2100
   or v_data->>'status' is distinct from 'confirmed' then raise exception 'Invalid settings' using errcode='22023'; end if;
  insert into public.media_bulletin_settings values(1,coalesce(v_current,0)+1,v_data)
   on conflict(id) do update set revision=excluded.revision,payload=excluded.payload;
 else raise exception 'Unsupported catalog operation' using errcode='22023';
 end if;
 update public.media_catalog_version set revision=revision+1 where id=1;
 return jsonb_build_object('saved',true,'revision',v_revision+1);
end; $$;
revoke all on function public.media_edit_catalog(bigint,text,jsonb) from public,anon,authenticated;
grant execute on function public.media_edit_catalog(bigint,text,jsonb) to authenticated;

create or replace function public.media_register_file(p_record jsonb)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare v_file public.media_files%rowtype;
begin
 insert into public.media_files(digest,filename,size,drive_id,item_id,item)
 values(p_record->>'digest',p_record->>'filename',(p_record->>'size')::bigint,p_record->>'drive_id',p_record->>'item_id',p_record)
 on conflict(digest) do nothing;
 select * into v_file from public.media_files where digest=p_record->>'digest';
 return to_jsonb(v_file);
end; $$;
grant select,insert on public.media_files to service_role;
revoke all on function public.media_register_file(jsonb) from public,anon,authenticated;
grant execute on function public.media_register_file(jsonb) to service_role;
create or replace function public.media_catalog_snapshot(p_day date,p_service text,p_revision bigint)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare v_work public.media_works%rowtype; v_current jsonb;
begin
 if auth.uid() is null or not exists(select 1 from public.media_members where user_id=auth.uid() and active) then
  raise exception 'Active membership required' using errcode='42501';
 end if;
 if p_day is null or p_service is null or p_service not in ('wednesday','friday','sunday') or p_revision is null or p_revision<0 then
  raise exception 'Invalid snapshot request' using errcode='22023';
 end if;
 select * into v_work from public.media_works where day=p_day and service=p_service;
 v_current:=jsonb_build_object('revision',coalesce(v_work.revision,0),'data',coalesce(v_work.payload,'{}'::jsonb),'updated_at',v_work.updated_at);
 if coalesce(v_work.revision,0)<>p_revision then
  return jsonb_build_object('matched',false,'current',v_current);
 end if;
 return jsonb_build_object('matched',true,'catalog_revision',(select revision from public.media_catalog_version where id=1),'day',p_day,'service',p_service,'work',v_current,'tables',jsonb_build_object(
  'songs',(select coalesce(jsonb_agg(to_jsonb(t) order by id),'[]'::jsonb) from public.media_songs t),
  'files',(select coalesce(jsonb_agg(to_jsonb(t) order by digest),'[]'::jsonb) from public.media_files t),
  'song_assets',(select coalesce(jsonb_agg(to_jsonb(t) order by song_id,digest),'[]'::jsonb) from public.media_song_assets t),
  'reviews',(select coalesce(jsonb_agg(to_jsonb(t) order by song_id,digest),'[]'::jsonb) from public.media_asset_reviews t),
  'attachments',(select coalesce(jsonb_agg(to_jsonb(t) order by slot),'[]'::jsonb) from public.media_attachments t where day=p_day and service=p_service),
  'settings',(select coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) from public.media_bulletin_settings t),
  'runtime_assets',(select coalesce(jsonb_agg(to_jsonb(t) order by path),'[]'::jsonb) from public.media_runtime_assets t)
 ));
end;
$$;
revoke all on function public.media_catalog_snapshot(date,text,bigint) from public,anon,authenticated;
grant execute on function public.media_catalog_snapshot(date,text,bigint) to authenticated;


create or replace function public.media_confirm_job(p_id uuid,p_file_id text,p_revision bigint,p_catalog_revision bigint)
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_job public.media_jobs%rowtype; v_work public.media_works%rowtype; v_catalog bigint; v_data jsonb; v_current jsonb;
begin
 if not exists(select 1 from public.media_members where user_id=auth.uid() and active and role in ('admin','editor')) then
  raise exception 'Active membership required' using errcode='42501'; end if;
 select revision into v_catalog from public.media_catalog_version where id=1 for share;
 if p_catalog_revision is null or v_catalog<>p_catalog_revision then
  raise exception 'Catalog changed' using errcode='40001'; end if;
 select * into v_job from public.media_jobs where id=p_id and status='succeeded';
 if not found or v_job.result->>'file_id' is distinct from p_file_id
   or v_job.snapshot->>'catalog_revision' is distinct from p_catalog_revision::text
   or jsonb_typeof(v_job.result->'unresolved') is distinct from 'array' or jsonb_array_length(v_job.result->'unresolved')<>0
   or v_job.result->'verification'->>'rendered' is distinct from 'true' then
  raise exception 'Verified production result required' using errcode='22023'; end if;
 perform pg_advisory_xact_lock(hashtextextended(v_job.day::text||':'||v_job.service,0));
 select * into v_work from public.media_works where day=v_job.day and service=v_job.service for update;
 if not found or v_work.revision is distinct from p_revision then
  raise exception 'Work changed' using errcode='40001'; end if;
 v_data:=v_work.payload;
 if v_data->'fields' is distinct from v_job.snapshot->'work'->'data'->'fields'
  or (v_data->'outputs'->v_job.output->>'fileId' is not null and v_data->'outputs'->v_job.output->>'fileId' is distinct from p_file_id)
  or coalesce((v_data->'outputs'->v_job.output->>'changed')::boolean,false) then
  raise exception 'Production input changed' using errcode='22023'; end if;
 if v_job.output='ppt' and exists(select 1 from unnest(array[
   'fridayMode','songChoices','songEditions','assetChoices','extraSongs','scriptureIds','fridayNoticeGroups','noticePrayerGroups','prayerTopicIds']) k
   where coalesce(v_job.snapshot->'work'->'data'->k,'null'::jsonb) is distinct from coalesce(v_data->k,'null'::jsonb))
   then raise exception 'Production selection changed' using errcode='22023'; end if;
 v_data:=jsonb_set(v_data,array['outputs'],coalesce(v_data->'outputs','{}'::jsonb));
 if v_data->'outputs'->v_job.output->>'fileId' is null then
  v_data:=jsonb_set(v_data,array['outputs',v_job.output],jsonb_build_object('fileId',p_file_id,
    'filename',v_job.result->>'filename','generated',true,'changed',false,'complete',false,
    'unresolved',v_job.result->'unresolved','format',case when v_job.output='pdf' then 'pdf' else 'pptx' end));
 end if;
 v_data:=jsonb_set(v_data,array['outputs',v_job.output,'complete'],'true');
 v_data:=jsonb_set(v_data,array['outputs',v_job.output,'archiveStatus'],'"uploaded"');
 v_current:=public.media_save_work(v_job.day,v_job.service,p_revision,v_data);
 return v_current->'current';
end; $$;
revoke all on function public.media_confirm_job(uuid,text,bigint,bigint) from public,anon,authenticated;
grant execute on function public.media_confirm_job(uuid,text,bigint,bigint) to authenticated;
commit;
