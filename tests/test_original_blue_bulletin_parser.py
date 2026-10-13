"""Tests that the ORIGINAL bulletin parser recognizes data without guessing PPT songs.

Synthetic extraction text follows the structure of the 10/11 HWP upload:
merged table cells flatten to linear text. Never guess missing sermon or
where the hymn list should appear in the actual worship sequence.
"""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

PARSER = Path(__file__).resolve().parents[1] / (
    "src/media_automation/_legacy_migration/ui/notice-parser.js"
)

@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_original_notice_parser_handles_flattened_hwp_without_inventing_worship_order():
    extracted = """
주보 하늘빛기쁨교회
10/11
cf) 오후 예배 : 생명의 삶 5주차
찬양 : 79, 337, 382장
*예배 / 섬김 :
구 분
기 도
봉 헌 기 도
설 거 지
수요예배 기도
이 번 주
1 부
인도자
김예시
홍예시, 박예시
이예시
2 부
장예시
조예시
다 음 주
1 부
인도자
유예시
신예시, 정예시
오예시
2 부
배예시
강예시
*1면 –
*
*설교 중 읽을 말씀 ☞
<교회 소식>
1. 예배 후 소식 안내
<10월 사역 일정>
10/13(화) : 모임
<목장 말씀 나누기>
<단 1:8~9 / 믿음과 상황이 충돌할 때>
1. 질문 첫째
2. 질문 둘째
3. 질문 셋째
4. 질문 넷째
"""
    driver = """
    const parser=require(process.argv[1]);
    const fs=require('node:fs');
    const text=fs.readFileSync(0,'utf8');
    process.stdout.write(JSON.stringify(parser.parseBulletin(text)));
    """
    result=subprocess.run(
        ["node","-e",driver,str(PARSER)],input=extracted,
        capture_output=True,text=True,timeout=4,check=True,
    )
    data=json.loads(result.stdout)
    f=data["fields"]
    assert data["dateLabel"]=="10/11"
    assert data["songList"]=="79, 337, 382장"
    assert f["오후예배"]["value"]=="생명의 삶 5주차"
    assert f["2부 기도 담당자"]["value"]=="장예시"
    assert f["2부 봉헌기도 담당자"]["value"]=="조예시"
    assert f["목장 본문"]["value"]=="단 1:8~9"
    assert f["목장 제목"]["value"]=="믿음과 상황이 충돌할 때"
    assert f["질문 4"]["value"]=="질문 넷째"
    assert "성경 본문" not in f and "설교 제목" not in f
    assert "시작 찬양 1" not in f
