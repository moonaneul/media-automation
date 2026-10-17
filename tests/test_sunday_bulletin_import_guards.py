"""Regressions for importing Sunday HWP serving tables and bulletin cover number.

Fixtures are synthetic: never claim they validate the real 2026-10-18 HWP.
"""
import json
import subprocess
from pathlib import Path

import pytest

PARSER=Path("src/media_automation/web/original/ui/notice-parser.js").resolve()
HTML=Path("src/media_automation/web/original/ui/index.html")


def parse(raw, tables=None):
    driver="""const p=require(process.argv[1]);
      const raw=process.argv[2],tables=JSON.parse(process.argv[3]);
      console.log(JSON.stringify(p.parseBulletin(raw,tables)));"""
    return json.loads(subprocess.check_output(
        ["node","-e",driver,str(PARSER),raw,json.dumps(tables)],text=True))


FLATTENED="""주보 교회
10/18
*예배 / 섬김 :
구 분
기 도
봉헌기도
설거지
수요예배 기도
이번 주
1부
인도자
첫봉헌
세척담당
수요담당
2부
두번째기도
두번째봉헌
다음 주
1부
인도자
다음봉헌
다음설거지
다음수요
2부
다음기도
다음봉헌2
<목장 말씀 나누기>
<시 1:1 / 설교 제목>
1. 질문
"""


def serving_table(second_prayer="두번째기도", second_offering="두번째봉헌"):
    return {
        "rows":3,"columns":6,
        "cells":[
            {"row":0,"column":0,"rowspan":1,"colspan":2,"text":"구 분"},
            *[{"row":0,"column":i,"rowspan":1,"colspan":1,"text":v}
              for i,v in enumerate(("기 도","봉 헌 기 도","설 거 지","수요예배 기도"),2)],
            {"row":1,"column":0,"rowspan":2,"colspan":1,"text":"이번 주"},
            {"row":1,"column":1,"rowspan":1,"colspan":1,"text":"1 부"},
            {"row":2,"column":1,"rowspan":1,"colspan":1,"text":"2 부"},
            {"row":1,"column":2,"rowspan":1,"colspan":1,"text":"인도자"},
            {"row":1,"column":3,"rowspan":1,"colspan":1,"text":"첫봉헌"},
            {"row":1,"column":4,"rowspan":2,"colspan":1,"text":"설거지담당"},
            {"row":1,"column":5,"rowspan":2,"colspan":1,"text":"수요담당"},
            {"row":2,"column":2,"rowspan":1,"colspan":1,"text":second_prayer},
            {"row":2,"column":3,"rowspan":1,"colspan":1,"text":second_offering},
        ]
    }


def test_exact_flattened_hwp_restores_all_prayer_offering_and_serving_roles():
    # This matches the 10/18 source's *structure*, with synthetic people.
    for tables in (None, [], [{"rows":1,"columns":1,"cells":[{"row":0,"column":0,"text":"기타 안내"}]}]):
        result=parse(FLATTENED,tables)
        f=result["fields"]
        assert f["이번 주 1부 기도"]["value"] == "인도자"
        assert f["이번 주 1부 봉헌기도"]["value"] == "첫봉헌"
        assert f["이번 주 설거지"]["value"] == "세척담당"
        assert f["이번 주 수요예배 기도"]["value"] == "수요담당"
        assert f["2부 기도 담당자"]["value"] == "두번째기도"
        assert f["2부 봉헌기도 담당자"]["value"] == "두번째봉헌"
        assert f["다음 주 1부 봉헌기도"]["value"] == "다음봉헌"
        assert f["다음 주 2부 기도"]["value"] == "다음기도"
        assert f["다음 주 2부 봉헌기도"]["value"] == "다음봉헌2"
        assert "형식이 일치하지 않아" not in " ".join(result["unknown"])


@pytest.mark.parametrize("altered", [
    FLATTENED.replace("두번째기도\n두번째봉헌", "두번째기도"),
    FLATTENED.replace("봉헌기도\n설거지", "설거지\n봉헌기도"),
    FLATTENED.replace("2부\n두번째기도", "2부\n설거지"),
    FLATTENED.replace("다음봉헌2", "설거지"),
])
def test_broken_flattened_hwp_never_guesses_roles(altered):
    r=parse(altered,[])
    assert "2부 기도 담당자" not in r["fields"]
    assert "2부 봉헌기도 담당자" not in r["fields"]
    assert "이번 주 설거지" not in r["fields"]
    assert any("형식이 일치하지 않아" in msg for msg in r["unknown"])


def test_structured_hwp_uses_actual_row_and_column_not_dishwashing():
    result=parse(FLATTENED,[serving_table()])
    fields=result["fields"]
    assert fields["2부 기도 담당자"]["value"]=="두번째기도"
    assert fields["2부 봉헌기도 담당자"]["value"]=="두번째봉헌"
    assert fields["이번 주 설거지"]["value"]=="설거지담당"
    assert "표의 행·열 좌표" not in " ".join(result["unknown"])


def test_table_heading_is_not_substituted_for_offering_prayer():
    result=parse(FLATTENED,[serving_table(second_offering="설거지")])
    assert result["fields"]["2부 기도 담당자"]["value"]=="두번째기도"
    assert "2부 봉헌기도 담당자" not in result["fields"]
    assert any("표 제목이 인식" in msg for msg in result["unknown"])


@pytest.mark.parametrize("line,issue",[
    ("주보 13-42","13-42"),
    ("주보 호수: 13-42","13-42"),
    ("제13-42호","13-42"),
])
def test_only_explicit_issue_number_extracted(line,issue):
    assert parse(line)["fields"]["확정 주보 호수"]["value"]==issue
    assert "확정 주보 호수" not in parse("2026년 10월 18일")["fields"]


def test_bulletin_number_is_present_in_form_and_checked_before_build():
    html=HTML.read_text()
    assert "['주보 표지 · 호수',['확정 주보 호수']]" in html
    assert "해당 주에 확인된 주보 호수" in html
    assert "번호를 추정하거나 빈 표지로 제작하지 않습니다" in html
    assert "if(service==='sunday'&&fridayParsed&&bulletinRoles(label))continue" in html
    assert "structured.fields))if(!(service==='sunday'&&fridayParsed&&bulletinRoles(label)))" in html


def test_common_keyvalue_parser_cannot_replace_bulletin_serving_grid():
    html=HTML.read_text()
    assert "const bulletinRoles=label" in html
    assert "if(service==='sunday'&&fridayParsed&&bulletinRoles(label))continue;" in html
    assert "if(!(service==='sunday'&&fridayParsed&&bulletinRoles(label)))parsed[label]=field" in html
