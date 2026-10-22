"""Restore the supplied original bulletin PDF's typography and vector artwork.

The private reference is never published. Every weekly field is removed before
inserting current input; absent values remain blank. Imposition remains 4|1,2|3.
"""
from pathlib import Path
import os
import pymupdf as pdf
from media_automation.people import confirmed_titles, format_people

LAYOUT_VERSION = 'original-reference-260920-v10-sunday-pastor-preacher-default'
ROOT = Path(__file__).resolve().parents[3]


def wrap_original_text(text, font, size, width):
    """Keep closing punctuation with preceding text at a narrow column edge."""
    lines = []
    for paragraph in text.splitlines():
        line = ''
        for char in paragraph:
            if line and font.text_length(line + char, fontsize=size) > width:
                if char in '?!.,:;)]}？！。，':
                    boundary = line.rfind(' ')
                    if boundary > 0 and font.text_length(line[boundary:] + char, fontsize=size) <= width:
                        tail = line[boundary:]
                        line = line[:boundary]
                    else:
                        tail = line[-1]
                        line = line[:-1]
                    lines.append(line)
                    line = tail + char
                else:
                    lines.append(line)
                    line = char
            else:
                line += char
        lines.append(line)
    return lines


def render_original_bulletin(document, destination, *, cover_static=None, news_static=None, cover_photo=None):
    assets = Path(os.environ.get('MEDIA_BULLETIN_ASSETS', str(ROOT / 'assets/private/bulletin')))
    required = [assets/'original-design.pdf', assets/'original-regular.ttf', assets/'original-bold.ttf']
    if not all(p.is_file() for p in required):
        raise ValueError('기존 주보 원본 템플릿과 글꼴이 없습니다. 기존 디자인을 확인한 템플릿을 설치하세요.')
    doc = pdf.open(required[0])
    if len(doc) != 2 or any(abs(p.rect.width-841.86)>1 or abs(p.rect.height-595.28)>1 for p in doc):
        raise ValueError('기존 주보 템플릿의 A4 가로 두 면을 확인하세요.')
    if cover_photo:
        from .cover_photo import replace_cover_photo
        replace_cover_photo(doc[1],cover_photo)
    # The reference PDF places another image outside the cover, whose pale
    # edge bleeds into the right print margin. Keep that margin clean for both
    # the original seasonal cover and every uploaded replacement.
    doc[1].draw_rect(pdf.Rect(831.58,-1,doc[1].rect.width+1,doc[1].rect.height+1),
                     color=None,fill=(1,1,1),overlay=True)
    regular = pdf.Font(fontfile=str(required[1])); bold = pdf.Font(fontfile=str(required[2]))
    jobs = []
    columns = {}
    def slot(page, rect, text, size=10, weight=True, align='left', baseline=None, leading=15):
        jobs.append((page,pdf.Rect(rect),str(text or ''),size,weight,align,baseline,leading))
    w=document.worship
    def person(name):
        if not name:return ''
        titles=confirmed_titles()
        return format_people(name,titles)
    for y,name,prefix in [(82.5,w.praise_first,'1부 '),(99.6,w.praise_second,'2부 '),
                          (150.3,w.first_service_prayer,'1부 '),(168.3,w.second_service_prayer,'2부 '),
                          (237,w.first_service_offering_prayer,'1부 '),(254.16,w.second_service_offering_prayer,'2부 ')]:
        slot(0,(331,y,404,y+14),prefix+person(name) if name else '',9.62,baseline=y+9.02)
        if name:
            label = person(name)
            parts = label.rsplit(' ', 1)
            rank = parts[1] if len(parts) == 2 and parts[1] in set(confirmed_titles().values()) | {'자매'} else ''
            columns[(0, y)] = (prefix.strip(), parts[0] if rank else label, rank)
    for rect,text in [((174,133.5,245,147),w.separate_hymn),((174,219.5,245,233),w.offering_hymn),
                      ((155,271.5,262,285),w.scripture),((140,288,283,302),w.sermon_title),
                      ((174,305.3,262,319),w.decision_hymn)]:
        slot(0,rect,text,10,align='center',baseline=rect[1]+10)
    preacher=w.preacher or ''
    for y,name in [(60.2,w.leader),(288.1,preacher),(322.5,w.closing_prayer)]:
        if name and name.replace(' ','')=='이은철':name='이 은 철 목 사'
        slot(0,(331,y,404,y+14),name,10,baseline=y+10)
    table=[(108,408,w.first_service_prayer),(169,408,w.first_service_offering_prayer),
           (108,424.2,w.second_service_prayer),(169,424.2,w.second_service_offering_prayer),
           (108,440.3,w.next_week_first_service_prayer),(169,440.3,w.next_week_first_service_offering_prayer),
           (108,456.5,w.next_week_second_service_prayer),(169,456.5,w.next_week_second_service_offering_prayer)]
    for x,y,text in table:slot(0,(x,y-1,x+43,y+12),text,9,align='center',baseline=y+9)
    for y,dishes,prayer in [(416.1,w.this_week_dishwashing,w.this_week_wednesday_prayer),(448.4,w.next_week_dishwashing,w.next_week_wednesday_prayer)]:
        slot(0,(224,y-1,308,y+12),dishes,9,align='center',baseline=y+9)
        slot(0,(315,y-1,406,y+12),prayer,9,align='center',baseline=y+9)
    slot(0,(125,516,216,539),w.afternoon_service,9.5,align='center',baseline=531)
    cell=document.cell_group
    slot(0,(450,83,811,105),f'<{cell.scripture} / {cell.title}>' if cell.scripture and cell.title else '',10,align='right',baseline=96)
    for i in range(4):
        text=cell.questions[i] if i<len(cell.questions) else ''
        y=117+i*90
        slot(0,(450,y-1,811,y+74),f'{i+1}. {text}' if text else '',10,False,baseline=y+10,leading=15)
    slot(1,(22,49,406,127),'\n'.join(f'{i+1}. {t}' for i,t in enumerate(document.news.church_news)),10,False,baseline=61,leading=15.5)
    month=document.news.schedule_month
    slot(1,(22,137,406,153),f'<{month}월 사역 일정>' if month else '',10,baseline=149)
    slot(1,(22,158,406,243),'\n'.join((str(a)+' : ' if a else '')+str(b) for a,b in document.news.monthly_schedule),10,False,baseline=171,leading=15.5)
    slot(1,(447,25,520,42),'No. '+document.cover.bulletin_number if document.cover.bulletin_number else '',10,baseline=38)
    slot(1,(700,25,823,42),document.cover.date_text,10,align='right',baseline=38)
    if cover_static:
        # The supplied cover artwork contains its contact block as an image.
        # Refuse changed contact settings rather than silently print old details.
        expected = {'church_name':'하늘빛기쁨성서침례교회', 'senior_pastor':'이은철',
                    'address':'서울특별시 구로구 천왕로 36(천왕동) 센타프라자 601호',
                    'phone':'02-2611-9191', 'website':'https://hjbbc.or.kr'}
        for key,value in expected.items():
            if getattr(cover_static,key).replace(' ','') != value.replace(' ',''):
                raise ValueError('표지 이미지의 교회 기본 정보가 변경됐습니다. 수정된 기존 표지 원본을 등록하세요.')
        slot(1,(472,96,801,132),cover_static.slogan,23,align='center',baseline=121,leading=28)
        slot(1,(472,146,801,174),' '.join(cover_static.verse_lines),9,align='center',baseline=157,leading=12)
    if news_static:
        for i,(label,value) in enumerate(news_static.meetings):
            x=26.9 if i<5 else 214.1;y=292.7+(i%5)*12.8
            slot(1,(x,y-1,x+181,y+11),'☞ '+label+' / '+value,8,False,baseline=y+8)
        slot(1,(30,411,399,441),news_static.mission,9,False,baseline=422,leading=13.5)
        for i,value in enumerate(news_static.core_values):
            x=32.6 if i<3 else 215.1;y=477.4+(i%3)*14.4
            slot(1,(x,y-1,x+182,y+12),f'{i+1}. {value}',9,False,baseline=y+9)
    # Always redraw serving names, including unchanged reference names. Preserve
    # the original cover and other explicitly unchanged artwork typography.
    import re
    def normalized(value):
        return re.sub(r'\s+', '', value)
    jobs = [job for job in jobs if not job[2] or
            (job[0] == 0 and (407 <= job[1].y0 <= 457 or (job[0], job[1].y0) in columns)) or
            normalized(doc[job[0]].get_textbox(job[1])) != normalized(job[2])]
    # Remove intersecting text only, preserving table strokes and background art.
    for page,rect,*_ in jobs:doc[page].add_redact_annot(rect,fill=False)
    for page in doc:page.apply_redactions(images=0,graphics=0,text=0)
    for page,rect,text,size,weight,align,baseline,leading in jobs:
        if not text:continue
        font=bold if weight else regular;name='OriginalBold' if weight else 'OriginalRegular'
        doc[page].insert_font(fontname=name,fontfile=str(required[2 if weight else 1]))
        if (page, rect.y0) in columns:
            prefix, person_name, rank = columns[(page, rect.y0)]
            # Match the supplied praise rows' measured prefix/name/title columns.
            for x, label in [(331.98, prefix), (351.69, person_name), (383.139, rank)]:
                if label:
                    limit = 383.139 if x == 351.69 and rank else rect.x1
                    if x + font.text_length(label, fontsize=size) > limit:
                        raise ValueError('담당자 표기가 기존 주보 열 너비를 넘습니다: '+text)
                    doc[page].insert_text((x, baseline), label, fontname=name, fontsize=size, color=(0,0,0))
            continue
        lines=wrap_original_text(text,font,size,rect.width-2)
        if baseline+(len(lines)-1)*leading>rect.y1-1:
            label = ('교회 소식' if page == 1 and rect.x0 == 22 and rect.y0 == 49 else
                     '월간 일정' if page == 1 and rect.x0 == 22 and rect.y0 == 158 else
                     '설교 제목' if page == 0 and rect.x0 == 140 else
                     '목장 말씀 제목·본문' if page == 0 and rect.x0 == 450 and rect.y0 == 83 else
                     '목장 질문' if page == 0 and rect.x0 == 450 else '담당자·예배 정보')
            raise ValueError(f'주보의 「{label}」 내용이 인쇄 영역을 넘습니다. 해당 내용을 줄여 주세요: '+text[:35])
        for i,line in enumerate(lines):
            width=font.text_length(line,fontsize=size)
            x=rect.x0+(rect.width-width)/2 if align=='center' else rect.x1-width if align=='right' else rect.x0
            doc[page].insert_text((x,baseline+i*leading),line,fontname=name,fontsize=size,color=(0,0,0))
    doc.select([1,0])
    doc.subset_fonts()
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    doc.save(destination,garbage=4,deflate=True)
    doc.close()
    return destination
