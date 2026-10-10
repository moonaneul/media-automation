# 2026-10-10 검토 갱신
현행 우선 시험안과 실제 금요 제작 메모리 측정은 online-operating-plan.md를 따른다. 아래 Cloudflare 중심 안은 이전 잠정안이다. 온라인 배포와 OneDrive 가져오기는 아직 미검증이다.

# 온라인 배포 및 OneDrive 연결 준비

현재 상태: 로컬 검증용. 온라인 배포와 Microsoft 계정 연결은 아직 수행하지 않았다.

## 무료 운영 조건 및 잠정 배포안
사용자 확정 조건: 월 비용 없이 무료만 사용. 개인 Microsoft 계정 OneDrive.

공용 웹과 가벼운 API는 Cloudflare Workers/정적 자산 무료 구간, 공동 입력은 D1 무료 구간, 원본·완료 파일은 기존 OneDrive를 후보로 검토한다. 유료 서버·디스크를 생성하거나 결제하지 않는다. 무료 한도 초과 시 자동 과금으로 전환하지 않고 작업 중단과 안내로 처리한다.

기존 Python/SQLite 로컬 검증 서버를 Cloudflare에 그대로 올릴 수는 없다. API는 Workers 런타임에 맞게 이전하고 DB는 D1으로 바꿔야 한다. Workers 무료 CPU 한도 때문에 현재 Python PPT 제작·LibreOffice 렌더링을 해당 서버에 직접 실행하는 안은 사용하지 않는다. 공용 웹 무료 배포 가능성과 PPT·PDF 제작 엔진의 무료 상시 실행 가능성은 별개의 검증 항목이다. 제작 엔진 실행 환경은 아직 미확정이며, 모든 기기에서 제작 가능하다는 요구를 검증 없이 완료라고 보고하지 않는다.

기존 OneDrive의 남은 용량도 확인한다. 요금제 업그레이드를 전제로 하지 않는다. 무료 서비스의 이용 조건과 제작 작업의 적합성을 확인한 후 구현 방향을 확정한다.

## 배포 전 코드 보완
현재 Python 기본 HTTP 서버는 로컬 검증용이므로 운영용 웹 서버로 교체한다. 외부 HTTPS 주소와 허용 Origin을 정확히 지정한다. 인증 쿠키에는 Secure를 적용한다. 공동 저장 실패·인증 만료 시 입력을 보존하고 재접속 화면을 제공한다. 서버 세션·업로드 작업·재시도는 재시작을 고려해 저장한다. 영상에는 범위 요청을 지원하고 업로드 형식은 실제 파일 내용도 검증한다. 팀원 목록은 공동 저장으로 이전한다. 금요 대면 선택을 추가하고 기존 대면 구성과 별도 연결한다.

SQLite는 영구 디스크의 단일 서버에서만 사용한다. 첨부 원본도 같은 영구 저장 영역에 둔다. 여러 서버로 확장하는 경우 DB와 원본 저장소를 분리한다. 백업과 복구를 검증한다.

## OneDrive 연결 순서
1. 개인 Microsoft 계정인지 교회 Microsoft 365 계정인지 확인한다.
2. 서비스용 Microsoft 앱을 등록하고 확정된 HTTPS 콜백 주소를 설정한다.
3. 담당자가 Microsoft 로그인과 파일 접근 동의 내용을 직접 확인한다.
4. 토큰은 서버에만 안전하게 저장한다. HTML·저장소·로그·채팅에 비밀값을 넣지 않는다.
5. 기존 공유 폴더의 실제 drive ID 및 폴더 item ID를 조회하고 읽기·쓰기 권한을 확인한다.
6. 찬양 자료실과 완료 PPT·주보 폴더를 각각 확인한다. 테스트 파일 업로드·조회로 검증한다.
7. 신규 원본 자동 업로드와 완료 파일 보관 큐를 연결한다. 성공 응답과 파일 정보를 확인한 후에만 보관 완료로 표시한다.

대용량 영상은 업로드 세션으로 분할 전송한다. 재시도 시 기존 파일을 덮어쓰지 않고 파일 식별값과 저장 이력을 확인한다. 원본 보유와 사용 허락은 구분한다. Microsoft API 권한 범위가 선택 폴더보다 넓을 수 있으므로 동의 단계에서 실제 범위를 표시한다.

## 아직 필요한 사용자 정보
- 월 서버 비용: 무료만 사용으로 확정
- OneDrive 계정: 개인 Microsoft 계정으로 확정
- 배포 서비스 로그인 및 결제 단계(필요 시 사용자 진행)
- 실제 운영 비밀번호 설정(사용자 직접 입력)

## 공식 근거
- https://render.com/docs/disks
- https://render.com/docs/free
- https://render.com/pricing
- https://learn.microsoft.com/en-us/graph/api/shares-get?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow

- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/d1/reference/faq/
