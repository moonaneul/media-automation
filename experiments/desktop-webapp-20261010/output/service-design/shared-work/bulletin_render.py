"""Render shared weekly fields using the existing church bulletin page layout."""
import sys,json,re
from pathlib import Path
sys.path.insert(0,'/Users/LOCAL_USER/Documents/media-automation/src')
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.units import mm
from media_automation.bulletin.document import BulletinCoverPage,BulletinWorshipPage,BulletinCellGroupPage,BulletinNewsPage
from media_automation.bulletin.cover import draw_cover_page,register_korean_fonts,FONT_REGULAR
from media_automation.bulletin.worship_page import draw_worship_page
from media_automation.bulletin.cell_group_page import draw_cell_group_page,wrap_text
from media_automation.bulletin.news_page import draw_news_page,BulletinNewsStatic

def render(payload):
 fields=payload['data']['fields'];base=payload['settings'];annual=base['annual'];church=base['church']
 def value(key):
  f=fields.get(key,{});return f.get('value','') if f.get('state')=='VALUE' else ''
 date=payload['date'];y,m,d=map(int,date.split('-'));date_text=f'{y}년 {m}월 {d}일'
 def lines(k):return tuple(v.strip() for v in value(k).splitlines() if v.strip())
 worship=BulletinWorshipPage(leader=value('주일 인도자'),praise_first=value('1부 찬양 인도자'),praise_second=value('2부 찬양 인도자'),separate_hymn=value('별도 찬송'),first_service_prayer=value('이번 주 1부 기도'),second_service_prayer=value('2부 기도 담당자'),offering_hymn=value('봉헌 찬송'),first_service_offering_prayer=value('이번 주 1부 봉헌기도'),second_service_offering_prayer=value('2부 봉헌기도 담당자'),scripture=value('성경 본문'),sermon_title=value('설교 제목'),closing_prayer=value('폐회 기도 담당자'),decision_hymn=value('결단 찬송'),this_week_dishwashing=value('이번 주 설거지'),this_week_wednesday_prayer=value('이번 주 수요예배 기도'),next_week_first_service_prayer=value('다음 주 1부 기도'),next_week_second_service_prayer=value('다음 주 2부 기도'),next_week_first_service_offering_prayer=value('다음 주 1부 봉헌기도'),next_week_second_service_offering_prayer=value('다음 주 2부 봉헌기도'),next_week_dishwashing=value('다음 주 설거지'),next_week_wednesday_prayer=value('다음 주 수요예배 기도'),afternoon_service=value('오후예배'))
 cell=BulletinCellGroupPage(scripture=value('목장 본문'),title=value('목장 제목'),questions=tuple(value('질문 '+str(i)) for i in range(1,5)))
 schedule=[]
 for line in lines('월간 사역 일정'):
  pair=re.split(r'\s*[:：]\s*',line,maxsplit=1);schedule.append((pair[0],pair[1] if len(pair)>1 else ''))
 month=re.search(r'(\d+)월',value('월간 일정 제목'))
 news=BulletinNewsPage(church_news=tuple(re.sub(r'^\d+[.)]\s*','',v) for v in lines('교회 소식')),monthly_schedule=tuple(schedule),schedule_month=int(month[1]) if month else None)
 static=BulletinNewsStatic(meetings=tuple(base['meeting_times'].items()),mission=church['사명선언문'],core_values=tuple(church['핵심가치']))
 register_korean_fonts()
 from media_automation.bulletin.document import BulletinDocument
 from media_automation.bulletin.cover import BulletinCoverStatic
 import approved_bulletin_layout as approved
 cover_static=BulletinCoverStatic(church_name=church['교회명'],slogan=annual['표어'],senior_pastor=church['담임목사'],address=church['주소'],phone=church['전화'],website=church['홈페이지'],verse_lines=tuple(wrap_text(annual['표어 보조 문구']+' ('+annual['관련 성경 구절']+')',font_name=FONT_REGULAR,font_size=8.1,max_width=124.5*mm)))
 approved.BulletinCoverStatic=lambda:cover_static
 approved.BulletinNewsStatic=lambda:static
 document=BulletinDocument(cover=BulletinCoverPage(value('확정 주보 호수'),date_text),worship=worship,cell_group=cell,news=news)
 photo=Path('/Users/LOCAL_USER/Documents/media-automation/assets/bulletin/autumn_soft_v2.png')
 approved.render_modern_bulletin(document,payload['output'],photo)
 missing=[k for k in ['성경 본문','설교 제목','별도 찬송','봉헌 찬송','결단 찬송','이번 주 1부 기도','2부 기도 담당자','이번 주 1부 봉헌기도','2부 봉헌기도 담당자','목장 본문','목장 제목'] if fields.get(k,{}).get('state','UNSET')=='UNSET']
 return {'unresolved':missing,'page_count':2,'complete':False,'imposition':[[4,1],[2,3]],'common_fields':{k:value(k) for k in ['성경 본문','설교 제목','별도 찬송','봉헌 찬송','결단 찬송','2부 기도 담당자','2부 봉헌기도 담당자']}}
if __name__=='__main__':
 p=json.loads(Path(sys.argv[1]).read_text());print(json.dumps(render(p),ensure_ascii=False))
