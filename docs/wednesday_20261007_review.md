# 2026-10-07 수요 자료 점검

## 확정된 입력

- 기도: 한미선 자매
- 본문: 삼상 18:6~11
- 설교 제목: 질투에 사로잡히면
- 추가 말씀: 없음

## 악보 등록 상태

| 등록 위치 | 곡명 | 장수 |
|---|---|---:|
| opening_song_1.pptx | 눈을 들어 하늘 보라 (515장) | 8 |
| opening_song_2.pptx | 성령의 봄바람 불어오니 (193장) | 9 |
| opening_song_3.pptx | 내 맘이 낙심되며 (300장) | 12 |
| additional_song.pptx | 나의 백성이 다 겸비하여 | 10 |
| decision_hymn.pptx | 나의 갈 길 다 가도록 (384장) | 15 |

GitHub e74ea0b의 이번 주 입력과 LFS 악보 다섯 파일을 사용했다.
지난주 내용이나 유사한 곡으로 대체하지 않았다.

## 검증 범위

Linux의 Open XML 병합기로 최종 74장 PPT 제작 및 최종 QA가 통과했다.
4:3, 전환 빈 화면, 본문, 정렬, 파란 도형, URL 검사가 통과했으며 링크 520개를 제거했다.
원본 악보 다섯 파일에 포함된 이미지가 최종 PPT에 동일한 바이트로 유지되는 것을 대조했다.
실제 macOS 실행과 PowerPoint 화면의 악보 잘림 및 가독성 확인은 아직 남아 있다.
구조 검증용 프리뷰는 최종 악보 병합본과 구분한다.

```bash
python scripts/sync_workspace.py pull &&
python wednesday.py complete 2026-10-07
open "output/wednesday/20261007_수요예배.pptx"
```

화면 확인 후 `python scripts/sync_workspace.py push`로 최종 파일을 동기화한다.
