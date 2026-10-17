begin;
create table if not exists public.media_runtime_assets (
 path text primary key, digest text not null references public.media_files(digest)
);
alter table public.media_runtime_assets enable row level security;
revoke all on public.media_runtime_assets from public,anon,authenticated;
grant select on public.media_runtime_assets to authenticated;
drop policy if exists media_runtime_team_read on public.media_runtime_assets;
create policy media_runtime_team_read on public.media_runtime_assets for select to authenticated using
 (exists(select 1 from public.media_members m where m.user_id=(select auth.uid()) and m.active));

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
 return jsonb_build_object('matched',true,'day',p_day,'service',p_service,'work',v_current,'tables',jsonb_build_object(
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

create table if not exists public.media_jobs (
 id uuid primary key default gen_random_uuid(), queued_by uuid not null references auth.users(id),
 request_key uuid not null, day date not null, service text not null, revision bigint not null,
 output text not null check(output in ('ppt','pdf')), groups jsonb not null,
 snapshot jsonb not null, status text not null default 'queued' check(status in ('queued','running','succeeded','failed')),
 created_at timestamptz not null default now(), deadline timestamptz not null default now()+interval '15 minutes',
 execution text, result jsonb, finished_at timestamptz,
 unique(queued_by,request_key)
);
alter table public.media_jobs enable row level security;
revoke all on public.media_jobs from public,anon,authenticated;
grant select,update on public.media_jobs to service_role;
grant select on public.media_members to service_role;
grant select on public.media_jobs to authenticated;
drop policy if exists media_jobs_team_read on public.media_jobs;
create policy media_jobs_team_read on public.media_jobs for select to authenticated using
 (exists(select 1 from public.media_members m where m.user_id=(select auth.uid()) and m.active));

create or replace function public.media_start_job(p_day date,p_service text,p_revision bigint,p_output text,p_groups jsonb,p_request_key uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_user uuid:=auth.uid(); v_job public.media_jobs%rowtype; v_snapshot jsonb;
begin
 if v_user is null or not exists(select 1 from public.media_members where user_id=v_user and active) then
  raise exception 'Active membership required' using errcode='42501';
 end if;
 if p_output is null or p_output not in ('ppt','pdf') or (p_output='pdf' and p_service<>'sunday')
  or p_request_key is null or p_groups is null or jsonb_typeof(p_groups)<>'array'
  or octet_length(p_groups::text)>65536 then raise exception 'Invalid production request' using errcode='22023'; end if;
 perform pg_advisory_xact_lock(hashtextextended('church-media-production-queue',0));
 select * into v_job from public.media_jobs where queued_by=v_user and request_key=p_request_key;
 if found then
  if v_job.day is distinct from p_day or v_job.service is distinct from p_service or v_job.revision is distinct from p_revision
    or v_job.output<>p_output or v_job.groups<>p_groups then
   raise exception 'Request key reused with different input' using errcode='22023';
  end if;
  return jsonb_build_object('queued',true,'id',v_job.id,'status',v_job.status,'reused',true);
 end if;
 update public.media_jobs set status='failed',finished_at=now(),result='{"error":"제작 시간이 만료됐습니다. 입력을 확인하고 다시 요청하세요."}'
  where status in ('queued','running') and deadline<now();
 if exists(select 1 from public.media_jobs where status in ('queued','running')) then
  return jsonb_build_object('queued',false,'busy',true);
 end if;
 v_snapshot:=public.media_catalog_snapshot(p_day,p_service,p_revision);
 if not (v_snapshot->>'matched')::boolean then return v_snapshot; end if;
 insert into public.media_jobs(queued_by,request_key,day,service,revision,output,groups,snapshot)
  values(v_user,p_request_key,p_day,p_service,p_revision,p_output,p_groups,v_snapshot) returning * into v_job;
 return jsonb_build_object('queued',true,'id',v_job.id,'status',v_job.status,'reused',false);
end;
$$;
revoke all on function public.media_start_job(date,text,bigint,text,jsonb,uuid) from public,anon,authenticated;
grant execute on function public.media_start_job(date,text,bigint,text,jsonb,uuid) to authenticated;

create or replace function public.media_claim_job(p_id uuid,p_execution text)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare v_job public.media_jobs%rowtype;
begin
 if p_execution is null or length(p_execution) not between 1 and 200 then
  raise exception 'Execution identifier required' using errcode='22023';
 end if;
 update public.media_jobs j set status='running',execution=p_execution
  where j.id=p_id and j.status='queued' and j.deadline>now()
   and exists(select 1 from public.media_members where user_id=j.queued_by and active)
  returning j.* into v_job;
 if not found then return jsonb_build_object('claimed',false); end if;
 return jsonb_build_object('claimed',true,'id',v_job.id,'snapshot',v_job.snapshot,'groups',v_job.groups,'output',v_job.output);
end;
$$;
revoke all on function public.media_claim_job(uuid,text) from public,anon,authenticated;
grant execute on function public.media_claim_job(uuid,text) to service_role;

create or replace function public.media_finish_job(p_id uuid,p_execution text,p_success boolean,p_result jsonb)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare v_id uuid;
begin
 if p_success is null or p_result is null or jsonb_typeof(p_result)<>'object' or octet_length(p_result::text)>2097152 then
  raise exception 'Invalid job result' using errcode='22023';
 end if;
 update public.media_jobs j set status=case when p_success then 'succeeded' else 'failed' end,
  result=p_result,finished_at=now()
  where j.id=p_id and j.status='running' and j.execution=p_execution and j.deadline>now()
   and exists(select 1 from public.media_members where user_id=j.queued_by and active)
  returning j.id into v_id;
 if v_id is null then raise exception 'Job completion not accepted' using errcode='42501'; end if;
 return jsonb_build_object('finished',true,'id',v_id);
end;
$$;
revoke all on function public.media_finish_job(uuid,text,boolean,jsonb) from public,anon,authenticated;
grant execute on function public.media_finish_job(uuid,text,boolean,jsonb) to service_role;
commit;
