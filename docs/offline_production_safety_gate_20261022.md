# 제작·실패 복구·공동 작업: 운영 데이터 비접촉 격리 검수

기준일: 2026-10-22. 이 문서는 **실제 Supabase, OneDrive, Cloud Run을 이용한 통합 테스트가 아니다.**
외부 연결을 차단하고 임시 SQLite 파일과 합성 결과물을 사용한 **오프라인 제작 흐름 검증**을 운영 배포 전에 추가한 기록이다.

## 운영을 바꾸지 않고 확인하는 항목

1. 수요·금요·주일 PPT와 주일 PDF: 별도 임시 작업 입력을 동결하고 `worker.execute()`의 제작 → 렌더 확인 → 서비스별 저장 위치 선정 → 결과물/미리보기/검수 보고서 업로드 → 작업 결과 기록 흐름을 Mock 환경에서 점검한다. 제작 및 업로드는 시험 대역이며 실제 예배 PPT/주보 PDF 결과물이 아님.
2. 네트워크는 `socket.socket.connect`와 `connect_ex`를 테스트 중 금지하여 외부 프로젝트/OneDrive 접속 시 실패하게 한다. 경로는 pytest `tmp_path`만 사용한다.
3. 업로드 1·2·3번째 단계의 오류, 생성 실패, 렌더 실패, 작업 취소, 완료 응답 불확실성을 주입하여 이전 승인본이 수정되지 않고 성공으로 표시되지 않는지 확인한다.
4. 동일 제작 작업 두 번 실행: 같은 ID에 두 번째 `claim`이 실패하여 중복 업로드를 시작하지 않는지 시험한다. **실제 Supabase의 원자적 job claim RPC 동작은 별도 DB 테스트가 필요하다.**
5. 두 작업자 동시 저장: 서로 다른 WorkStore 클라이언트가 동일한 SQLite 데이터베이스의 같은 주차를 동시에 저장하면 하나만 성공하고 하나는 revision 충돌을 반환하는지 검증한다. 다른 예배의 내용은 유지한다. **실제 Supabase SQL 함수의 트랜잭션/회원권한 테스트는 아직 미실시.**
6. 실제 PyMuPDF로 *합성* A4 PDF 2쪽 렌더·형식 검사를 수행하고 1쪽 PDF, A4 세로 PDF를 거부하는지 확인한다. 이는 주보 원본과 개역개정 본문을 사용한 출력 검수와 다르다.

## 오프라인 전용 CI

`.github/workflows/offline-production-safety.yml`은 `fix/ui-workflow-20261015` 브랜치에서 관련 시험 파일과 workflow가 변경되면 테스트를 실행한다.
`GOOGLE_APPLICATION_CREDENTIALS`, Supabase 환경변수, 제작 Job ID 등이 비어 있는지 검사하며 GCP 인증/배포 명령을 실행하지 않는다.

```bash
python -m pytest -q --tb=short \
  tests/test_isolated_cloud_production.py \
  tests/test_cloud_worker_archive_paths.py \
  tests/test_workflow_races.py \
  tests/test_reviewed_worship_completion.py \
  tests/test_cloud_catalog_audit.py \
  tests/test_cloud_source_classification.py
```

## 확인되지 않은 것과 운영 전 중단 조건

- 실제 기존 악보 PPT·금요 Zoom MP4/MP3·개역개정 본문·4쪽 주보를 사용한 완성본 렌더링 검수 **미실시**.
- 실 Supabase의 RLS와 회원 로그인, 동일 작업 중복 dispatch, 취소/만료 처리의 DB 원자성 **미실시**.
- 실 OneDrive의 파일 권한, 업로드 후 다운로드 해시 검증, 실패 시 원격에 남는 부분 업로드 및 중복 방지 **미실시**.
- 공유 클라우드 환경에서 여러 기기의 실시간 갱신·동시 편집 시나리오 **미실시**.
- 미리보기 Cloud Run은 정적 UI이므로 실제 제작 API를 호출해도 정상 수행되지 않는다.
- 운영 웹 `media-automation`/작업 Job `media-production` 변경 금지. 별도 테스트 Supabase + OneDrive 안전 저장소 + 계정 권한 경계를 검증하고 운영 변경 승인 전에는 자동화하지 않는다.

## 다음 단계

1. 이 오프라인 CI를 실행해 성공 여부 확인.
2. 서버/Job과 **완전히 분리된 테스트 Supabase 프로젝트·테스트 Microsoft 저장소**를 사용할 경우 필요한 권한/비용/보존 정책을 먼저 설계. 단순히 기존 Secret Manager 값을 새 서비스에 연결하지 않는다.
3. 그 뒤 실제 템플릿/성경/악보 원본을 사용하지 않는 독립 시험부터 진행하고, 예배용 출력을 만들 때는 실제 담당자 안내·개역개정·자산 사용 허락·사람 눈으로 렌더 검수한다.
4. 실제 운영 전 복구 지점으로 기존 웹 리비전·Job digest·Supabase 백업/복구 경로를 기록하고 *변경 없는 사전 검수*와 명시적 배포 승인을 받는다.
