"""Map explicit original web fields to the official four-page bulletin model."""
import json
import re
import uuid
from pathlib import Path
from datetime import date
from media_automation.bulletin.document import BulletinDocument, BulletinCoverPage, BulletinWorshipPage, BulletinCellGroupPage, BulletinNewsPage
from media_automation.bulletin.original_design import render_original_bulletin, LAYOUT_VERSION
from media_automation.bulletin.cover import BulletinCoverStatic
from media_automation.bulletin.news_page import BulletinNewsStatic
from .generation import current_input, ROOT, BUILD_VERSION


def bulletin_hymn_label(text):
    if not text:return text
    match=re.match(r'^\s*(?:새찬송가\s*|찬송가\s*)?(\d+)\s*장(?:\s|$)', text)
    return match[1]+'장' if match else text


def default_sunday_leader(fields, church):
    """Use the confirmed church pastor only when no weekly leader was supplied.

    An explicit current-week VALUE overrides the default; NONE stays absent.
    Never inherit a previous worship week's assigned leader.
    """
    selected = fields.get('주일 인도자', {})
    if selected.get('state') == 'NONE':
        return None
    if selected.get('state') == 'VALUE':
        return selected.get('value') or None
    pastor = str(church.get('담임목사') or '').strip()
    if not pastor:
        return None
    return pastor if pastor.endswith('목사') else pastor + ' 목사'


def generate_bulletin(store, body):
    if body['service'] != 'sunday': raise ValueError('주보는 주일 작업에서 제작합니다.')
    data = current_input(store, body)
    fields = dict(data.get('fields', {}))
    # Sunday worship and cell-group passage/title share the explicit current input.
    for source,target in [('성경 본문','목장 본문'),('설교 제목','목장 제목')]:
        if fields.get(source,{}).get('state') in ('VALUE','NONE'):
            if fields.get(target,{}).get('state')=='VALUE' and fields[target].get('value')!=fields[source].get('value'):
                raise ValueError('예배와 목장의 '+source+' 값이 다릅니다. 공통 입력을 수정해 확인하세요.')
            fields[target]=dict(fields[source])
    def value(label):
        f = fields.get(label, {})
        return f.get('value') if f.get('state') == 'VALUE' else None
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS bulletin_settings (id INTEGER PRIMARY KEY, revision INTEGER, payload TEXT)')
        row = db.execute('SELECT payload FROM bulletin_settings WHERE id=1').fetchone()
    settings = json.loads(row[0]) if row else json.loads(Path(__file__).with_name('bulletin-base-reference.json').read_text())
    annual, church = settings['annual'], settings['church']
    worship_leader = default_sunday_leader(fields, church)
    unresolved = [label for label in ('확정 주보 호수', '성경 본문', '설교 제목', '목장 본문', '목장 제목', *['질문 '+str(n) for n in range(1,5)]) if not value(label)]
    unresolved += [label for label in ('주일 인도자','설교자','1부 찬양 인도자','2부 찬양 인도자','폐회 기도 담당자','별도 찬송','봉헌 찬송','결단 찬송', '이번 주 1부 기도','2부 기도 담당자','이번 주 1부 봉헌기도','2부 봉헌기도 담당자',
        '이번 주 설거지','이번 주 수요예배 기도','다음 주 1부 기도','다음 주 2부 기도',
        '다음 주 1부 봉헌기도','다음 주 2부 봉헌기도','다음 주 설거지','다음 주 수요예배 기도') if fields.get(label,{}).get('state','UNSET')=='UNSET' and not (label == '주일 인도자' and worship_leader)]
    if settings.get('reference_year') != date.fromisoformat(body['date']).year:
        raise ValueError('해당 연도의 표어를 확인하고 설정을 갱신하세요.')
    if settings.get('status') != 'confirmed': unresolved.append('표어·고정 정보:확인 필요')
    mapping = dict(leader='주일 인도자', praise_first='1부 찬양 인도자', praise_second='2부 찬양 인도자',
        preacher='설교자', closing_prayer='폐회 기도 담당자', separate_hymn='별도 찬송', offering_hymn='봉헌 찬송',
        scripture='성경 본문', sermon_title='설교 제목', decision_hymn='결단 찬송', afternoon_service='오후예배',
        first_service_prayer='이번 주 1부 기도', second_service_prayer='2부 기도 담당자',
        first_service_offering_prayer='이번 주 1부 봉헌기도', second_service_offering_prayer='2부 봉헌기도 담당자',
        this_week_dishwashing='이번 주 설거지', this_week_wednesday_prayer='이번 주 수요예배 기도',
        next_week_first_service_prayer='다음 주 1부 기도',next_week_second_service_prayer='다음 주 2부 기도',
        next_week_first_service_offering_prayer='다음 주 1부 봉헌기도',next_week_second_service_offering_prayer='다음 주 2부 봉헌기도',
        next_week_dishwashing='다음 주 설거지',next_week_wednesday_prayer='다음 주 수요예배 기도')
    worship = BulletinWorshipPage(**{k:worship_leader if k == 'leader' else
        bulletin_hymn_label(value(v)) if k in ('separate_hymn','offering_hymn','decision_hymn') else value(v)
        for k,v in mapping.items()})
    schedule = []
    for line in (value('월간 사역 일정') or '').splitlines():
        parts = re.split(r'\s*[:：]\s*',line,maxsplit=1)
        schedule.append(tuple(parts) if len(parts)==2 else ('',line))
    month = re.search(r'(\d+)월', value('월간 일정 제목') or '')
    document = BulletinDocument(
        BulletinCoverPage(value('확정 주보 호수') or '',f"{date.fromisoformat(body['date']).year}년 {date.fromisoformat(body['date']).month}월 {date.fromisoformat(body['date']).day}일"),
        worship,
        BulletinCellGroupPage(value('목장 본문'),value('목장 제목'),tuple(value('질문 '+str(n)) or '' for n in range(1,5))),
        BulletinNewsPage(tuple(re.sub(r'^\s*\d+[.)]\s*','',line) for line in (value('교회 소식') or '').splitlines()),tuple(schedule),int(month[1]) if month else None))
    cover = BulletinCoverStatic(church_name=church['교회명'], slogan=annual['표어'],senior_pastor=church['담임목사'],
        address=church['주소'],phone=church['전화'], website=church['홈페이지'],
        verse_lines=(annual['표어 보조 문구']+' ('+annual['관련 성경 구절']+')',))
    news = BulletinNewsStatic(meetings=tuple(settings['meeting_times'].items()),mission=church['사명선언문'],core_values=tuple(church['핵심가치']))
    directory = Path(store.path).with_suffix('.generated'); directory.mkdir(parents=True,exist_ok=True)
    ident = uuid.uuid4().hex; file = directory/(ident+'.pdf')
    try:
        render_original_bulletin(document,file,cover_static=cover,news_static=news,cover_photo=settings.get('cover_photo'))
        report=dict(layout_version=LAYOUT_VERSION,format='pdf',date=body['date'],service='sunday',fields=data.get('fields',{}),effective_fields=fields,unresolved=unresolved,
            complete=False,visual_review_pending=True,settings=settings,settings_revision=json.loads(row[0]) if row else None,
            derived_defaults={'주일 인도자': worship_leader} if worship_leader and fields.get('주일 인도자', {}).get('state', 'UNSET') == 'UNSET' else {})
        (directory/(ident+'.json')).write_text(json.dumps(report,ensure_ascii=False))
        return dict(engine_version=BUILD_VERSION,layout_version=LAYOUT_VERSION,file_id=ident,format='pdf',filename=body['date']+'-주보-검수전.pdf',
            page_count=2,issue_number=value('확정 주보 호수'),unresolved=unresolved,complete=False,visual_review_pending=True)
    except Exception:
        file.unlink(missing_ok=True);raise
