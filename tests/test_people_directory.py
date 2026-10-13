import json
import pytest
from media_automation.people import confirmed_titles,format_people


def test_private_directory_supports_confirmed_titles_and_keeps_unknown_names(tmp_path):
    p=tmp_path/'people.json';p.write_text(json.dumps(dict(schema_version=1,people={'검증이름':'사모','다른이름':'자매'})))
    titles=confirmed_titles(p)
    assert format_people('검증이름, 다른이름',titles)=='검증이름 사모, 다른이름 자매'
    assert format_people('미등록이름',titles)=='미등록이름'
    assert format_people('검증이름 집사',titles)=='검증이름 집사'
    assert format_people('인도자',titles)=='인도자'
    assert format_people('다른이름 자매',titles)=='다른이름 자매'


def test_directory_is_reloaded_after_change(tmp_path):
    p=tmp_path/'people.json'
    for title in ['형제','집사']:
        p.write_text(json.dumps(dict(schema_version=1,people={'검증이름':title})))
        assert confirmed_titles(p)['검증이름']==title


def test_invalid_title_is_not_silently_inferred(tmp_path):
    p=tmp_path/'people.json';p.write_text(json.dumps(dict(schema_version=1,people={'검증이름':'추정'})))
    with pytest.raises(ValueError):confirmed_titles(p)
