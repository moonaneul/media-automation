# 주일예배 악보 PPT 등록

이번 주 주일예배 안내를 `python sunday.py start <안내파일>` 또는
`python sunday.py paste`로 입력한 뒤, 악보 PPT를 슬롯별로 등록합니다.

```bash
python sunday.py song-register YYYY-MM-DD 1 "받은악보.pptx"
python sunday.py song-register YYYY-MM-DD offering "받은악보.ppt"
```

슬롯은 `1`, `2`, `3`(시작 찬양), `separate`(별도 찬송),
`offering`(봉헌 찬송), `special`(특송), `decision`(결단 찬송)입니다.
이번 주 체크리스트에 없는 슬롯은 등록할 수 없습니다.

`.pptx`는 원본을 주간 폴더에 복사합니다. `.ppt`는 Microsoft PowerPoint에서
`.pptx` 복사본으로 변환합니다. 원본은 수정하지 않습니다. 기존 슬롯 파일을
교체하려면 `--replace`를 명시해야 합니다.

등록 직후 체크리스트를 갱신합니다. 모든 필요한 악보가 준비되면 주일 `resume`
흐름을 실행합니다. 다른 필수 입력까지 준비되었으면 찬양 manifest도 갱신됩니다.
준비 상태는 다음 명령으로 확인합니다.

```bash
python sunday.py status YYYY-MM-DD
python sunday.py resume YYYY-MM-DD
```

과거 주차 자료나 비슷한 제목의 악보는 자동으로 선택하지 않습니다. 악보가 없으면
해당 화면은 빈 상태로 두며, 사용 전 곡명·찬송가 번호·필요한 절과 후렴을 확인합니다.
