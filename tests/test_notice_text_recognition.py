import json
import subprocess
from pathlib import Path

PARSER=Path('src/media_automation/web/original/ui/notice-parser.js').resolve()
TEXT='''3곡 찬양: 이하은 자매
기도: 한미선 자매
광고
찬양 1곡:
말씀 봉독: 삼상 18:6~11 / 질투에 사로잡히면
읽을 말씀:
결단 찬송: 384장
폐회 기도: 이은철 목사'''


def run(code):
    return json.loads(subprocess.check_output(['node','-e',"const p=require(process.argv[1]);"+code,str(PARSER)],text=True))


def test_headerless_actual_wednesday_notice():
    result=run('console.log(JSON.stringify(p.parseWednesday('+json.dumps(TEXT)+')));')
    assert result['fields']['성경 본문']['value']=='삼상 18:6~11'
    assert result['fields']['설교 제목']['value']=='질투에 사로잡히면'
    assert result['fields']['추가 말씀']=={'state':'NONE','value':''}
    assert result['fields']['추가 찬양']=={'state':'NONE','value':''}
    assert result['unknown']==[]
    html=Path('src/media_automation/web/original/ui/index.html').read_text()
    assert "if(service==='wednesday'){fridayParsed=NoticeParser.parseWednesday(raw)" in html


def test_common_body_title_across_all_services_and_prefixes():
    for service in ('wednesday','friday','sunday'):
        result=run("console.log(JSON.stringify(p.parseCommon('. 말씀 봉독: 삼상 18:6~11 / 질투에 사로잡히면',['성경 본문','설교 제목'],{},"+json.dumps(service)+")));" )
        assert result['fields']['성경 본문']['value']=='삼상 18:6~11'
        assert result['fields']['설교 제목']['value']=='질투에 사로잡히면'


def test_split_labels_and_explicit_empty_remain_distinct():
    result=run("console.log(JSON.stringify(p.parseCommon('본문\\n요 3:16\\n설교 제목\\n하나님의 사랑\\n읽을 말씀:', ['성경 본문','설교 제목','추가 말씀'],{},'sunday')));")
    assert result['fields']['성경 본문']['value']=='요 3:16'
    assert result['fields']['설교 제목']['value']=='하나님의 사랑'
    assert result['fields']['추가 말씀']['state']=='NONE'
    assert '기도 담당자' not in result['fields']
