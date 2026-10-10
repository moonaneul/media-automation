"""Optional modern preview; retains the same weekly document and page contents."""
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from media_automation.bulletin.cover import FONT_REGULAR, register_korean_fonts, draw_bold_slogan, BulletinCoverStatic
from media_automation.bulletin.cell_group_page import wrap_text
from media_automation.bulletin.worship_page import build_worship_order_rows, build_serving_rows
from media_automation.bulletin.news_page import BulletinNewsStatic
from media_automation.bulletin.pdf import build_imposition_plan


class Page:
    def __init__(self, canvas, offset):
        self.c = canvas
        self.x = offset
        self.width = 148.5
        self.left = 12
        self.right = 136.5

    def text(self, text, x, top, size=9, bold=False, right=False):
        self.c.setFillColorRGB(0, 0, 0)
        if bold:
            width = pdfmetrics.stringWidth(text, FONT_REGULAR, size)
            center = self.x + x * mm + (-width / 2 if right else width / 2)
            draw_bold_slogan(self.c, text, center, (210 - top) * mm, size)
        else:
            self.c.setFont(FONT_REGULAR, size)
            method = self.c.drawRightString if right else self.c.drawString
            method(self.x + x * mm, (210 - top) * mm, text)

    def para(self, text, top, size=9, leading=4.6, x=12, width=124.5):
        for line in wrap_text(text, font_name=FONT_REGULAR, font_size=size, max_width=width * mm):
            if top > 198:
                raise ValueError('주보 내용이 페이지 영역을 넘습니다.')
            self.text(line, x, top, size)
            top += leading
        return top

    def rule(self, top):
        self.c.setStrokeColorRGB(.82, .82, .82)
        self.c.setLineWidth(.35)
        self.c.line(self.x + self.left * mm, (210-top)*mm,
                    self.x + self.right * mm, (210-top)*mm)

    def title(self, text):
        self.text(text, 12, 21, 18, bold=True)
        self.rule(27)

    def section(self, text, top):
        self.text(text, 12, top, 10, bold=True)
        return top + 7


def cover(p, document, photo):
    data = document.cover
    static = BulletinCoverStatic()
    if not data.bulletin_number:
        raise ValueError('주보 호수가 없습니다.')
    p.text(f'No. {data.bulletin_number}', 12, 13, 8.5)
    p.text(data.date_text, 136.5, 13, 8.5, right=True)
    p.text('영혼 구원하여', 12, 31, 22, bold=True)
    p.text('제자 삼는 교회', 12, 42, 22, bold=True)
    top = 53
    for line in static.verse_lines:
        top = p.para(line, top, size=8.1, leading=4.2)
    # The image itself dissolves to white; display it whole without a hard crop.
    from PIL import Image
    with Image.open(photo) as im:
        iw, ih = im.size
    scale = min(148.5 * mm / iw, 103 * mm / ih)
    image_width, image_height = iw * scale, ih * scale
    p.c.drawImage(str(photo), p.x + (148.5*mm-image_width)/2,
                  (210-61)*mm-image_height,
                  width=image_width, height=image_height)
    # Keep the church identity and contact information together as one footer.
    def centered(text, top, size, bold=False):
        text_width = pdfmetrics.stringWidth(text, FONT_REGULAR, size) / mm
        p.text(text, (148.5 - text_width) / 2, top, size, bold=bold)

    centered(static.church_name, 177, 16, bold=True)
    centered('담임목사 이 은 철', 185, 8.5)
    centered(static.address, 192, 7.6)
    centered('전화 (02)2611-9191   ·   홈페이지 https://hjbbc.or.kr', 198, 7.6)


def worship(p, document):
    page = document.worship
    p.title('오전 예배 순서')
    top = 34
    if page.leader:
        p.text(f'인도 : {page.leader}', 136.5, top, 8.5, right=True)
        top += 6
    for label, value in build_worship_order_rows(page):
        p.text(''.join(label.split()), 12, top, 9)
        lines = wrap_text(value, font_name=FONT_REGULAR, font_size=9, max_width=88*mm)
        for index, line in enumerate(lines):
            p.text(line, 136.5, top+index*4.2, 9, right=True)
        top += max(6, len(lines)*4.2+1.8)
    top += 7
    top = p.section('예배 / 섬김', top)
    positions = (12, 44, 66, 91, 119)
    sizes = (8, 7.8, 7.8, 7.5, 7.5)
    headers = ('구분', '기도', '봉헌기도', '설거지', '수요기도')
    for text, x, size in zip(headers, positions, sizes):
        p.text(text, x, top, size, bold=True)
    p.rule(top+2)
    top += 8
    for row in build_serving_rows(page):
        for text, x, size in zip(row, positions, sizes):
            p.text(text, x, top, size)
        top += 7
    p.rule(top-3)
    top += 7
    # Same three meeting blocks and same contents as the current bulletin.
    columns = ((12, '주일 오전', '(오전 9:00)', ('학생부 예배',)),
               (55, '주일 오후', '(오후 1:30)', (page.afternoon_service or '',)),
               (99, '수요 예배', '(오후 7:30)', ('찬양 다 같이', '말씀 이은철 목사', '합심기도 다 같이')))
    for x, title, time, lines in columns:
        p.text(title, x, top, 9, bold=True)
        p.text(time, x, top+5, 8)
        cursor = top+13
        for line in lines:
            for wrapped in wrap_text(line, font_name=FONT_REGULAR, font_size=8, max_width=37*mm):
                p.text(wrapped, x, cursor, 8)
                cursor += 4.6
        if cursor > 198:
            raise ValueError('주보 2쪽 모임 안내가 페이지를 넘습니다.')


def cell_group(p, document):
    page = document.cell_group
    p.title('목장 말씀 나누기')
    if len(page.questions) != 4:
        raise ValueError('목장 질문은 4개여야 합니다.')
    p.text(page.scripture or '', 12, 37, 9)
    title_bottom = p.para(page.title or '', 47, size=16, leading=7)
    top = max(65, title_bottom+10)
    slot = (198-top)/4
    for index, question in enumerate(page.questions):
        cursor = top+index*slot
        p.text(f'{index+1:02d}', 12, cursor, 11, bold=True)
        end = p.para(question, cursor, size=9.5, leading=5, x=24, width=112.5)
        if end+10 > cursor+slot:
            raise ValueError('목장 질문과 필기 여백이 페이지를 넘습니다.')


def news(p, document):
    page = document.news
    static = BulletinNewsStatic()
    p.title('교회 소식')
    top = 36
    for index, item in enumerate(page.church_news, 1):
        p.text(f'{index:02d}', 12, top, 9, bold=True)
        top = p.para(item, top, x=23, width=113.5, size=9, leading=4.7)+2
    top += 3
    top = p.section(f'{page.schedule_month}월 사역 일정' if page.schedule_month else '사역 일정', top)
    for date, content in page.monthly_schedule:
        top = p.para(f'{date}  {content}', top, size=8.5, leading=4.5)+2
    top += 4
    top = p.section('예배 / 모임 안내', top)
    meeting_top = top
    for column, values in enumerate((static.meetings[:5], static.meetings[5:])):
        cursor = meeting_top
        for label, time in values:
            x = 12+column*64
            p.text(f'{label} / {time}', x, cursor, 7.1)
            cursor += 6
    top = meeting_top+34
    p.rule(top-3)
    top = p.section('하늘빛기쁨교회 사명선언문', top+4)
    top = p.para(static.mission, top, size=8, leading=4.3)+4
    top = p.section('하늘빛기쁨교회 핵심가치', top)
    for column, values in enumerate((static.core_values[:3], static.core_values[3:])):
        for index, value in enumerate(values):
            p.text(f'{index+column*3+1}. {value}', 12+column*64, top+index*5, 7.7)
    top += 20
    p.para(f'* {static.joy_meaning}', top, size=7.1, leading=3.8)


def render_modern_bulletin(document, output, photo):
    register_korean_fonts()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    c = Canvas(str(output), pagesize=landscape(A4))
    c.setTitle(f'{document.cover.date_text} 주보 · 가을 디자인 시안')
    drawers = {1:cover, 2:worship, 3:cell_group, 4:news}
    for sheet in build_imposition_plan():
        for number, offset in ((sheet.left_page, 0), (sheet.right_page, landscape(A4)[0]/2)):
            c.saveState()
            p = Page(c, offset)
            if number == 1:
                drawers[number](p, document, photo)
            else:
                drawers[number](p, document)
            c.restoreState()
        c.showPage()
    c.save()
    return output
