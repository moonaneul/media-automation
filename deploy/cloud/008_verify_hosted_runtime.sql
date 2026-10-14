-- Run AFTER 007. All synthetic database writes are rolled back.
-- No files are downloaded/uploaded, no Cloud Run job is invoked.
begin;
select set_config('request.jwt.claims',jsonb_build_object('sub',(
 select user_id from public.media_members where active and role='admin' order by user_id limit 1
),'role','authenticated')::text,true);
set local role authenticated;
do $$
declare v_revision bigint; v_song text:=gen_random_uuid()::text; v_saved jsonb; v_job jsonb; v_work jsonb;
begin
 if auth.uid() is null then raise exception 'An existing active admin is required'; end if;
 begin
  perform 1 from public.media_sessions;
  raise exception 'Sessions exposed to browser role';
 exception when insufficient_privilege then null; end;
 begin
  perform public.media_claim_job(gen_random_uuid(),'browser');
  raise exception 'Browser can claim worker job';
 exception when insufficient_privilege then null; end;
 select revision into v_revision from public.media_catalog_version where id=1;
 v_saved:=public.media_edit_catalog(v_revision,'song',jsonb_build_object('song',jsonb_build_object(
  'id',v_song,'title','ROLLBACK 검증곡','aliases','[]'::jsonb,'edition',null,'number',null,'assets','[]'::jsonb)));
 if v_saved->>'saved'<>'true' then raise exception 'Catalog write failed'; end if;
 v_saved:=public.media_edit_catalog(v_revision,'remove','{}'::jsonb);
 if v_saved->>'saved'<>'false' then raise exception 'Stale catalog write was accepted'; end if;
 v_work:=public.media_save_work('2099-01-07','wednesday',0,'{"fields":{"설교 제목":{"state":"VALUE","value":"ROLLBACK 시험"}}}');
 if v_work->>'saved'<>'true' then raise exception 'Synthetic work write failed'; end if;
 v_job:=public.media_start_job('2099-01-07','wednesday',1,'ppt','[]'::jsonb,gen_random_uuid());
 if v_job->>'busy'='true' then raise exception 'An existing production is active. Verify later without altering it.'; end if;
 if v_job->>'queued'<>'true' then raise exception 'Queue start failed'; end if;
 perform set_config('media.test_job_id',v_job->>'id',true);
end; $$;
reset role;
set local role service_role;
do $$
declare v_id uuid:=current_setting('media.test_job_id')::uuid; v_result jsonb;
begin
 v_result:=public.media_dispatch_job(v_id);
 if v_result->>'dispatch'<>'true' then raise exception 'Dispatch CAS failed'; end if;
 v_result:=public.media_dispatch_job(v_id);
 if v_result->>'dispatch'<>'false' then raise exception 'Duplicate dispatch accepted'; end if;
 v_result:=public.media_claim_job(v_id,'rollback-execution');
 if v_result->>'claimed'<>'true' then raise exception 'Worker claim failed'; end if;
 v_result:=public.media_claim_job(v_id,'duplicate');
 if v_result->>'claimed'<>'false' then raise exception 'Duplicate claim accepted'; end if;
 v_result:=public.media_job_active(v_id,'wrong-execution');
 if v_result->>'active'<>'false' then raise exception 'Wrong execution active'; end if;
 begin
  perform public.media_finish_job(v_id,'wrong-execution',true,'{}');
  raise exception 'Wrong execution can finish';
 exception when insufficient_privilege then null; end;
end; $$;
reset role;
set local role authenticated;
select public.media_cancel_job(current_setting('media.test_job_id')::uuid);
reset role;
set local role service_role;
do $$
declare v_id uuid:=current_setting('media.test_job_id')::uuid; v_result jsonb;
begin
 v_result:=public.media_job_active(v_id,'rollback-execution');
 if v_result->>'active'<>'false' then raise exception 'Cancelled job active'; end if;
 begin
  perform public.media_finish_job(v_id,'rollback-execution',true,'{}');
  raise exception 'Cancelled job can succeed';
 exception when insufficient_privilege then null; end;
end; $$;
reset role;
select 'hosted_runtime_verification_passed_rollback_only' as result;
rollback;
