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
