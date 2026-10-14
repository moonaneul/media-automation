-- Apply only to the church-media project.
begin;
create table if not exists public.media_works (
  day date not null,
  service text not null check (service in ('wednesday','friday','sunday')),
  revision bigint not null check (revision > 0),
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  updated_at timestamptz not null default now(),
  updated_by uuid not null references auth.users(id),
  primary key (day,service)
);
create table if not exists public.media_work_revisions (
  day date not null,
  service text not null check (service in ('wednesday','friday','sunday')),
  revision bigint not null check (revision > 0),
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  updated_at timestamptz not null,
  updated_by uuid not null references auth.users(id),
  primary key (day,service,revision)
);
alter table public.media_works enable row level security;
alter table public.media_work_revisions enable row level security;
revoke all on public.media_works, public.media_work_revisions from public, anon, authenticated;
grant select on public.media_works, public.media_work_revisions to authenticated;
drop policy if exists media_works_team_read on public.media_works;
create policy media_works_team_read on public.media_works for select to authenticated
using (exists (select 1 from public.media_members m where m.user_id=(select auth.uid()) and m.active));
drop policy if exists media_revisions_team_read on public.media_work_revisions;
create policy media_revisions_team_read on public.media_work_revisions for select to authenticated
using (exists (select 1 from public.media_members m where m.user_id=(select auth.uid()) and m.active));

-- The only client write path: validation, revision comparison, update and history
-- are one transaction. No client can bypass revision checks with a table UPDATE.
create or replace function public.media_save_work(p_day date, p_service text, p_expected_revision bigint, p_data jsonb)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  v_uid uuid := auth.uid();
  v_current public.media_works%rowtype;
  v_revision bigint;
  v_updated timestamptz;
  v_field jsonb;
begin
  if v_uid is null or not exists (
    select 1 from public.media_members where user_id=v_uid and active
  ) then raise exception 'Active membership required' using errcode='42501'; end if;
  if p_day is null or p_service is null or p_service not in ('wednesday','friday','sunday')
    or p_expected_revision is null or p_expected_revision<0
    or p_data is null or jsonb_typeof(p_data)<>'object'
    or octet_length(p_data::text)>1048576 then
    raise exception 'Invalid work input' using errcode='22023';
  end if;
  if p_data ? 'fields' then
    if jsonb_typeof(p_data->'fields')<>'object' then
      raise exception 'Invalid fields' using errcode='22023';
    end if;
    for v_field in select value from jsonb_each(p_data->'fields') loop
      if jsonb_typeof(v_field)<>'object' or not (v_field ? 'state')
        or (v_field->>'state') is null or (v_field->>'state') not in ('UNSET','NONE','VALUE')
        or (v_field ? 'value' and jsonb_typeof(v_field->'value')<>'string') then
        raise exception 'Invalid field state' using errcode='22023';
      end if;
      if ((v_field->>'state')='VALUE' and btrim(coalesce(v_field->>'value',''))='')
        or ((v_field->>'state')<>'VALUE' and coalesce(v_field->>'value','')<>'') then
        raise exception 'Field state/value mismatch' using errcode='22023';
      end if;
    end loop;
  end if;
  -- Also serializes concurrent first saves when there is no row to lock yet.
  perform pg_advisory_xact_lock(hashtextextended(p_day::text || ':' || p_service, 0));
  select * into v_current from public.media_works where day=p_day and service=p_service for update;
  if coalesce(v_current.revision,0)<>p_expected_revision then
    return jsonb_build_object('saved',false,'current',jsonb_build_object(
      'revision',coalesce(v_current.revision,0),'data',coalesce(v_current.payload,'{}'::jsonb),
      'updated_at',v_current.updated_at));
  end if;
  v_revision := p_expected_revision+1;
  v_updated := clock_timestamp();
  insert into public.media_works values (p_day,p_service,v_revision,p_data,v_updated,v_uid)
  on conflict (day,service) do update set revision=excluded.revision,payload=excluded.payload,
    updated_at=excluded.updated_at,updated_by=excluded.updated_by;
  insert into public.media_work_revisions values (p_day,p_service,v_revision,p_data,v_updated,v_uid);
  return jsonb_build_object('saved',true,'current',jsonb_build_object(
    'revision',v_revision,'data',p_data,'updated_at',v_updated));
end;
$$;
revoke all on function public.media_save_work(date,text,bigint,jsonb) from public,anon,authenticated;
grant execute on function public.media_save_work(date,text,bigint,jsonb) to authenticated;
-- An explicit membership check distinguishes an empty week from revoked access.
create or replace function public.media_get_work(p_day date, p_service text)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
  v_row public.media_works%rowtype;
begin
  if auth.uid() is null or not exists (
    select 1 from public.media_members where user_id=auth.uid() and active
  ) then raise exception 'Active membership required' using errcode='42501'; end if;
  if p_day is null or p_service is null or p_service not in ('wednesday','friday','sunday') then
    raise exception 'Invalid work key' using errcode='22023';
  end if;
  select * into v_row from public.media_works where day=p_day and service=p_service;
  return jsonb_build_object('revision',coalesce(v_row.revision,0),
    'data',coalesce(v_row.payload,'{}'::jsonb),'updated_at',v_row.updated_at);
end;
$$;
revoke all on function public.media_get_work(date,text) from public,anon,authenticated;
grant execute on function public.media_get_work(date,text) to authenticated;
commit;
select 'media work storage ready' as result;

-- Run after 002_media_works.sql. All test records are rolled back.
begin;
set local role authenticated;
select set_config('request.jwt.claims',
 '{"sub":"776e30f7-9dd3-4229-b9d4-23de72331f21","role":"authenticated"}', true);
do $$
declare
  v_day date := '9999-12-31';
  v_result jsonb;
  v_data jsonb := '{"fields":{"본문":{"state":"UNSET","value":""},"추가 말씀":{"state":"NONE","value":""}}}';
begin
  if exists(select 1 from public.media_works where day=v_day and service='wednesday') then
    raise exception 'Test date already in use; no existing record changed';
  end if;
  v_result := public.media_get_work(v_day,'wednesday');
  if v_result->>'revision'<>'0' or v_result->'data'<>'{}'::jsonb then
    raise exception 'Empty work check failed';
  end if;
  v_result := public.media_save_work(v_day,'wednesday',0,v_data);
  if v_result->>'saved'<>'true' or v_result->'current'->>'revision'<>'1' then
    raise exception 'First save failed';
  end if;
  v_result := public.media_save_work(v_day,'wednesday',0,'{}'::jsonb);
  if v_result->>'saved'<>'false' or v_result->'current'->'data'<>v_data then
    raise exception 'Conflict did not preserve latest work';
  end if;
  v_result := public.media_save_work(v_day,'wednesday',1,v_data);
  if v_result->>'saved'<>'true' or v_result->'current'->>'revision'<>'2'
    or (select count(*) from public.media_work_revisions where day=v_day and service='wednesday')<>2 then
    raise exception 'Revision history failed';
  end if;
  begin
    update public.media_works set payload='{}' where day=v_day and service='wednesday';
    raise exception 'Direct write unexpectedly allowed';
  exception when insufficient_privilege then null;
  end;
  begin
    perform public.media_save_work(v_day,'wednesday',2,
      '{"fields":{"본문":{"state":"NONE","value":"past data"}}}'::jsonb);
    raise exception 'Invalid field unexpectedly accepted';
  exception when invalid_parameter_value then null;
  end;
end;
$$;
-- A signed-in account without membership must not read or write via the RPC.
select set_config('request.jwt.claims',
 '{"sub":"00000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
do $$
begin
  begin
    perform public.media_get_work('9999-12-31','wednesday');
    raise exception 'Non-member read unexpectedly allowed';
  exception when insufficient_privilege then null;
  end;
  begin
    perform public.media_save_work('9999-12-31','wednesday',2,'{}');
    raise exception 'Non-member save unexpectedly allowed';
  exception when insufficient_privilege then null;
  end;
end;
$$;
set local role anon;
do $$
begin
  begin
    perform public.media_get_work('9999-12-31','wednesday');
    raise exception 'Anonymous access unexpectedly allowed';
  exception when insufficient_privilege then null;
  end;
end;
$$;
rollback;
select '저장·충돌·수정 이력·권한 검증 성공 (시험 자료는 취소됨)' as result;
