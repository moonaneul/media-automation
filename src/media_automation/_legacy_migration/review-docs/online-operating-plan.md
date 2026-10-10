# 맥북 없는 무료 온라인 운영 검토 — 2026-10-10

상태: 공식 조건 확인 및 로컬 제작 성능 측정 단계. 온라인 배포·OneDrive 인증·원격 파일 삽입은 미검증.

## 우선 시험할 구성
Oracle Always Free A1 Linux 서버에서 웹/API·Python 제작 엔진·SQLite를 운영하고, 기존 OneDrive에서 원본을 읽고 결과를 보관한다. GitHub는 소스 보관과 배포 검증에 사용한다. Cloudflare 계정은 첫 시험의 필수 조건으로 잡지 않는다. HTTPS 접속과 로그인 준비 전에는 교회 데이터를 인터넷에 공개하지 않는다.

Oracle 공식 한도는 A1 합계 2 OCPU·12GB RAM, 부트 디스크 포함 블록 저장소 200GB이다. 이 용량은 현재 제작 엔진을 시험할 근거이며 운영 성공의 증거는 아니다. 무료 서버 재고 부족 및 유휴 서버 회수 가능성이 있다. 계정 등록 시 카드 본인 확인이 필요할 수 있다. 유료 계정 전환·한도 초과 자원 생성은 하지 않는다. 계정 등록과 약관 동의는 사용자가 수행한다.

## 제외 또는 보류
- Cloudflare Workers Free: CPU 10ms, 요청 본문 100MB. 최근 제작 PPT 약 269MB. 현재 Python 제작·PPT 렌더링을 그대로 실행할 수 없다. 가벼운 웹/API 후보로만 둔다.
- Render Free: 512MB RAM, 임시 디스크. 현재 엔진의 대용량 ZIP 읽기 및 복사와 영구 DB 운영을 그대로 옮기기에는 제약이 있다. 별도 메모리 최적화·저장소 분리 전에는 주력으로 확정하지 않는다.
- Hugging Face: 신규 Docker/Gradio Spaces는 현재 유료 플랜 생성 조건이 있어 무료만 사용한다는 요구에 맞지 않는다.
- GitHub Actions: 소프트웨어 빌드·검증에 사용한다. 교회 PPT를 매주 생성하는 상시 앱 실행 서버로는 사용하지 않는다. 공식 약관의 서버리스 앱 및 저장소 소프트웨어와 무관한 작업 제한을 고려한다.

## 로컬 성능 측정
2026-10-10 금요 PPT 별도 생성: 35장, 269,234,805바이트, 21.8초. 부모 프로세스 최대 RSS 929,759,232바이트, 자식 프로세스 최대 RSS 676,806,656바이트. 두 피크를 합산하지 않는다. macOS 측정이므로 Linux 서버 속도·메모리·재생 성공으로 단정하지 않는다. 현재 부모 프로세스 피크만으로도 Render Free 512MB를 초과한다. 기존 주간 입력 및 웹의 결과 파일 ID는 변경하지 않았다.

## 실제 이전 작업
1. 맥북 절대 경로를 설정값으로 바꾸고 Python/Node/LibreOffice 및 한글 글꼴을 Linux에서 설치·검증한다.
2. 수요·주일·금요 템플릿과 승인 BGM을 별도 비공개 배포 자료로 준비한다. sources 원본은 수정하지 않는다. 주간 내용은 이전 자료에서 승계하지 않는다.
3. 금요 MP4 5개·MP3 4개가 들어간 결과를 서버에서 제작하여 PowerPoint 복구 경고·자동 재생·기도 음악 지속을 다시 검수한다.
4. 웹/API는 운영용 서버·HTTPS·인증·정확한 Origin 제한으로 교체한다. 영상 업로드·다운로드는 스트리밍/범위 요청으로 처리한다. 대용량 제작은 작업 큐로 한 번에 하나씩 실행한다.
5. 서버 재시작 뒤 입력·첨부·작업 상태 복구와 별도 백업을 검증한다.

## OneDrive 영상 가져오기 검증
개인 Microsoft 계정도 Graph v1.0의 파일 다운로드 API 및 위임 Files.Read 권한을 지원한다. 교회 조직 계정을 새로 만드는 것은 읽기 시험의 필수 조건이 아니다. 기존 로그인 오류가 해결됐다고 가정하지 않는다.

먼저 읽기 전용 권한으로 기존 폴더에서 영상 하나를 지정한다. 파일 이름·크기·파일 ID를 확인하고 원격 원본을 임시 영역에 받아 해시를 기록한다. PPT에 내장된 바이트와 비교한 뒤 PowerPoint에서 실제 영상·음성을 재생한다. 실패하면 직접 첨부한 다른 파일로 조용히 대체하지 않고 연결 실패를 표시한다. 다운로드 URL과 액세스 토큰은 로그·브라우저 저장소에 남기지 않는다. 완료 파일 보관은 읽기 검수 이후 별도 쓰기 동의와 업로드 성공 검수로 추가한다.

## 다음 외부 단계에 필요한 것
GitHub 계정은 사용자 보유 확인. Oracle 무료 계정·무료 서버 실제 확보 여부는 미확인. 기존 OneDrive 폴더 및 개인 계정 앱 등록/인증도 미완료. 계정 비밀번호·토큰을 채팅으로 받지 않는다.

## 공식 자료
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://www.oracle.com/cloud/free/faq/
- https://developers.cloudflare.com/workers/platform/limits/
- https://render.com/docs/free
- https://render.com/docs/compute-plans
- https://huggingface.co/docs/hub/en/spaces-overview
- https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features
- https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0
