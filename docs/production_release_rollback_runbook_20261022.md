# 교회 미디어 제작실: 운영 전환 및 장애 복구 절차 (초안, 2026-10-22)

**운영 승인 전 참고 문서. 지금은 실제 운영 웹/Job/Supabase/OneDrive를 변경하지 않는다.**

## 1. 확정된 기준 상태

- Google Cloud 프로젝트 `church-media-511519`, 리전 `asia-northeast3`.
- 운영 웹 서비스 `media-automation`: 2026-10-22에 확인된 기존 revision `media-automation-00004-hrt`.
- 운영 웹/제작 Job 기준 이미지: `asia-northeast3-docker.pkg.dev/church-media-511519/church-media/runtime-hosted@sha256:31b6839e918a8e75636d19bd86376a4515614f4a0d3a4e91e92bf3b029fe3be5`.
- 제작 Job `media-production`은 웹과 별도 배포 단위다. 웹 리비전 롤백만으로 Job 실행 이미지가 복구되지 않는다.
- `media-ui-preview-1022`는 정적 UI만 제공하며 실제 제작 API가 없어 독립 기능 스테이징 테스트의 대체물이 아니다.
- 운영 웹의 `MEDIA_PUBLIC_ORIGIN`과 Cloud Run의 유효 접속 URL/Host 검증이 맞는지 확인해야 한다. URL 변경 시 403일 수 있다.

## 2. 지금 실행할 수 있는 읽기 전용 사전 확인

검수 브랜치의 `deploy/cloud/read_only_release_gate.py`는 `describe`만 호출하고 비밀번호, Service Account 키, Secret Manager 값을 출력하지 않는다.

```bash
# 검수 브랜치의 최신 파일을 Cloud Shell에 가져온 다음:
python3 deploy/cloud/read_only_release_gate.py --live
```

보고서에서 `unexpected_operational_change`이 true면 **배포 절차를 중단하고 기준 상태 변경 원인을 확인**한다. 기존 기준값이 계획된 변경으로 인해 달라졌다면 이 스크립트의 baseline 수정은 신규 검토·승인 후 별도 수행해야 한다.

`authorized_for_production_deployment`는 의도적으로 false다. 기준 이미지가 유지된다는 사실만으로 실제 제작 기능 검수가 완료된 것으로 취급하지 않는다.

## 3. 운영 배포 허용을 위한 독립 검증 조건

- 별도 Supabase 프로젝트, 테스트 회원 계정/RLS, 실제 교회 자료와 분리된 OneDrive 테스트 폴더/계정. **기존 `church-media-supabase`, `church-media-onedrive-key`를 독립 스테이징 서비스에 그대로 넣지 않기**.
- 수요·금요 Zoom·금요 대면·주일 PPT, 주일 주보 PDF를 각각 실제 동결 작업 입력으로 제작. 금요 대면 여부는 사용자 공지로 지정하고 예배별 슬라이드 구성/디자인을 승계한다.
- 개역개정 본문 절/번호/침례 치환, 악보 PPT·MP4 재생, 주보 A4 양면 접지, 주요 순서 간 빈 화면, 각 화면 가독성/잘림의 **사람 눈 검수**.
- 교회에서 **사용 허락이 검증된** 악보/미디어를 사용하며, 소스나 영상의 보유 사실만으로 허락을 추정하지 않는다.
- 병렬 편집 중 충돌 표시, 서버에 저장됐으나 응답이 끊긴 경우 새로고침 후 복구, 중복 Job claim 방지, 제작 취소/시간초과, 업로드 중단/다운로드 SHA256 검증을 별도 테스트 데이터로 시험.
- 테스트 미디어 저장 경로에서 실패 후 남는 부분 업로드/원격 고아 파일을 조사하고, 기존 운영 완성본 자동 삭제/덮어쓰기를 막는다.
- 실제 로그인·Supabase/OneDrive 통합 시험의 실행 기록과 승인자를 확보하고 **웹과 Job을 별도로** 승격 승인한다.

## 4. 운영 반영 전 백업과 비교

- Cloud Run 웹 서비스 리비전/트래픽/환경변수 **이름** 및 실행 계정, Job 컨테이너 이미지, 모든 기존 비밀 참조/권한을 읽기 전용으로 기록한다. 비밀 **값**은 텍스트에 붙여 넣거나 저장하지 않는다.
- Supabase의 정확한 마이그레이션 SQL, DB 복구 방안, 스키마 역호환성을 확인하고, 실제 데이터 백업이 성공했는지 확인한다. 앱 이미지 되돌리기가 DB 변경까지 복구해 주지 않는다.
- 현재 성공한 제작 작업 ID와 보관 완료본의 식별자·해시·폴더 매핑을 보존하고, OneDrive 원본 및 sources/ 등 동기화 참고자료는 수정하지 않는다.
- 새 Cloud Run 이미지 배포 후 트래픽 변경 없이 점검할 수 있는 **별도 격리 서비스/스테이징**을 우선 활용한다. 같은 운영 서비스에 임시 태그만 붙이면 `MEDIA_PUBLIC_ORIGIN` 불일치 또는 실제 비밀정보 공유 위험이 있다.

## 5. 장애 시 판단과 복구 — 실행하지 않은 예시

운영 변경 승인 후 웹 롤백이 필요할 때 확인된 **이전 웹 revision이 보존되어 있고 호환성이 확인된 경우에만** 운영자가 다음 명령을 실행할 수 있다.

```bash
# !!! 예시. 현재 실행 금지. 먼저 실제 revision·DB 호환성·승인을 확인할 것.
gcloud run services update-traffic media-automation \
  --project=church-media-511519 \
  --region=asia-northeast3 \
  --to-revisions=media-automation-00004-hrt=100
```

제작 Job에 새 이미지가 이미 반영된 경우 웹만 복구해서는 불충분하다. 다음은 **별도 명시 승인** 및 기존 Job 환경변수/서비스 계정 설정 유지 여부를 검토한 후 사용할 수 있는 Job 이미지 복구 예시다.

```bash
# !!! 예시. 현재 실행 금지. 기존 설정 유지 여부를 확인할 것.
gcloud run jobs update media-production \
  --project=church-media-511519 \
  --region=asia-northeast3 \
  --image=asia-northeast3-docker.pkg.dev/church-media-511519/church-media/runtime-hosted@sha256:31b6839e918a8e75636d19bd86376a4515614f4a0d3a4e91e92bf3b029fe3be5
```

- 작업 실행 중 장애라면 큐 상태부터 확인하며, 결과가 불확실한 파일 업로드를 자동 재실행/덮어쓰기/삭제하지 않는다. 확인된 파일은 보관한다.
- Supabase 데이터/권한 문제라면 웹 이미지 전환과 무관하게 복구할 수 있다. 무작정 DB 롤백하지 않고 복구 시점과 이후 변경된 예배 자료의 보존 여부를 따진다.
- 사용자가 실제 화면에서 입력, 다운로드 및 원본/완료본 보관을 확인한 다음 복구 완료를 선언한다.

## 6. 현재 결론

현재까지 실행한 오프라인 안전 검수는 GitHub Actions #3 기준 **85 passed**이다. 이 테스트는 더미 데이터와 mocked cloud를 사용하므로 실제 로그인/원본/제작/업로드가 정상이라는 주장을 뒷받침하지 못한다.

**운영 승격 및 롤백 명령은 이번 단계에서 실제로 실행되지 않았다.**
