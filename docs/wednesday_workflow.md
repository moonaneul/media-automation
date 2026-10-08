# 수요예배 운영 워크플로 v1

수요예배 PPT 자동화의 사용자 진입점은 `wednesday.py`입니다.

금요 Zoom과 동일하게 **안내 입력 → REVIEW → 자료 준비 → complete** 흐름을 사용하되,
수요예배 고유의 4:3 디자인, 악보 PPT, 한 절당 한 화면 규칙을 유지합니다.

## 기본 사용

목사님/담당자가 보낸 이번 주 수요예배 안내를 클립보드에 복사한 뒤:

```bash
python wednesday.py paste
```

상태 확인:

```bash
python wednesday.py status YYYY-MM-DD
```

REVIEW가 필요한 경우:

```bash
python wednesday.py review YYYY-MM-DD
python wednesday.py ignore YYYY-MM-DD "문장"
python wednesday.py assign YYYY-MM-DD FIELD "문장"
python wednesday.py resume YYYY-MM-DD
```

## 악보 준비

사용자가 제공한 악보 PPT는 슬롯에 등록합니다.

```bash
python wednesday.py song-register YYYY-MM-DD 1 "받은파일.pptx"
python wednesday.py song-register YYYY-MM-DD additional "받은파일.ppt"
```

슬롯 이름:

```text
1 / 2 / 3     = 시작 찬양 1~3
additional    = 추가 찬양
decision      = 결단 찬송
```

- `.pptx`는 원본을 주간 작업 폴더에 복사합니다.
- `.ppt`는 원본을 수정하지 않고 Microsoft PowerPoint로 `.pptx` 복사본을 만든 뒤 등록합니다.
- 기존 슬롯 파일은 자동으로 덮어쓰지 않습니다. 교체가 맞을 때만 `--replace`를 추가합니다.
- 등록 직후 체크리스트와 찬양 manifest가 갱신됩니다.
- 이번 주 체크리스트에 없는 슬롯은 등록하지 않습니다.
- 과거 주차 파일이나 비슷한 제목의 파일을 자동 선택하지 않습니다.

등록 결과는 다음 폴더에 저장됩니다.

```text
input/wednesday/YYYYMMDD/
```

지원 슬롯:

```text
opening_song_1.pptx
opening_song_2.pptx
opening_song_3.pptx
additional_song.pptx
decision_hymn.pptx
```

내부 체크리스트와 빌드에서는 파일명이 **정확히 일치할 때만** 사용됩니다.

- 비슷한 파일명을 자동 추정하지 않습니다.
- 지난주 악보를 자동 대체하지 않습니다.
- 가사 PPT로 대체하지 않습니다.
- 사용자가 제공한 악보 사진을 잘라 PPT처럼 재구성하지 않습니다.
- 악보가 없으면 해당 찬양은 실제 결과에서 생략하며 제작자용 안내 문구를 띄우지 않습니다.

## 최종 생성

맥에서 입력·성경·악보 파일·구조를 검증할 때:

```bash
python wednesday.py complete YYYY-MM-DD --validate-only
```

이 명령은 `*_structure_check.pptx` 프리뷰를 만들며 최종 PPT를 새로 만들거나
기존 완성본을 덮어쓰지 않는다. 프리뷰의 악보 자리는 원본 장수만 반영한 빈 화면이다.
실제 악보 병합은 현재 Windows PowerPoint 환경에서 수행한다.
구조 QA 통과는 악보 곡명이 안내와 일치한다는 보증이 아니며 이미지 악보도 직접 확인해야 한다.

기본 수요 원본 참고 PPT는 다음 위치를 사용합니다.

```text
sources/수요예배.pptx
```

다른 파일을 사용할 경우 `--source`로 명시합니다.

```bash
python wednesday.py complete YYYY-MM-DD
```

또는:

```bash
python wednesday.py complete YYYY-MM-DD --source "경로/수요예배.pptx"
```

결과:

```text
output/wednesday/YYYYMMDD_수요예배.pptx
```

## 입력 상태

안내 파서는 다음을 구분합니다.

```text
provided = 항목과 값이 제공됨
blank    = 항목은 있으나 값이 비어 있음
missing  = 항목 자체가 안내에 없음
```

Weekly Data에서는 다음으로 변환됩니다.

```text
provided -> VALUE
blank    -> NONE
missing  -> 생성 중단
```

`missing`을 지난주 값으로 채우지 않습니다.

## 알려진 안내 표현

다음 형식은 기도 담당자로 인식합니다.

```text
기도(한송희)
```

다음 형식은 곡 제목으로 추정하지 않습니다.

```text
찬양3(이하은)
찬양 3곡(이하은)
찬양1
```

이는 찬양 개수/인도자 메타데이터일 수 있기 때문입니다.

`광고`, `폐회기도`, `찬양 담당`처럼 현재 수요 PPT 화면을 만들지 않는 알려진 항목은 REVIEW 오류로 취급하지 않습니다.

그 외 해석할 수 없는 일반 문장은 자동 추정하지 않고 REVIEW로 보냅니다.

## 성경

- 개역개정만 사용합니다.
- 등록된 본문 라이브러리를 우선 사용하고, 없으면 `data/private/bible_fixed.json`에서 조회합니다.
- JSON이 없을 때만 기존 검증 마스터를 사용합니다. JSON에 요청 절이 없으면 임의 대체하지 않고 중단합니다.
- 개역개정 통합 절은 원문 단위를 유지하고 `18~19`처럼 범위를 표시합니다. 통합 절 일부만 요청하면 중단합니다.
- AI가 본문을 생성하지 않습니다.
- 화면 표시 시 `세례 → 침례`를 적용합니다.
- 수요예배는 한 절당 한 화면입니다.

## 빈 화면

현재 운영 규칙:

```text
예배 전 안내
→ 빈 화면
→ 찬양1
→ 빈 화면
→ 찬양2
→ 빈 화면
→ 찬양3
→ 빈 화면
→ 기도
→ 빈 화면
→ 추가 찬양
→ 빈 화면
→ 성경 봉독
→ 빈 화면
→ 설교 제목
→ 빈 화면
→ 추가 말씀(있는 경우)
→ 빈 화면
→ 결단 찬송
```

같은 성경 본문 안에서 절이 바뀔 때는 빈 화면을 넣지 않습니다.

## QA

최종 생성 시 구조 프리뷰 QA와 실제 악보 병합본 QA를 모두 실행합니다.

자동 검사 항목:

- 약 4:3 비율
- 순서 전환 빈 화면
- 성경 절 수/절 번호
- 본문 범위 표기
- 본문 글자 크기와 줄간격
- `세례 → 침례`
- 기도/설교 제목 가로·세로 중앙 정렬
- 새 생성 화면의 파란 배경 도형
- URL/하이퍼링크

과거 수요 자료에서 확인된 AliExpress 링크 같은 불필요한 외부 링크도 최종 QA에서 탐지합니다.

## 마지막 사람 검수

자동 QA 통과와 실제 예배 사용 가능은 동일하지 않습니다.

최종 PPT는 PowerPoint에서 실제 렌더링하여 다음을 확인합니다.

- 악보 잘림
- 본문 잘림
- 본문 가독성
- 빈 화면 위치
- 곡 전체/필요 절/후렴 포함 여부
- 담당자/제목/본문 최종 일치
- 불필요한 객체

병합 전에는 `pytest`와 실제 과거 주차 E2E 테스트를 수행합니다.
