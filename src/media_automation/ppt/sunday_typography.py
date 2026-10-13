"""Sunday and Wednesday typography measured from the church's 2026-01-25 reference.

Update only generated text slides. Score and pre-service originals remain byte-identical.
"""
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
import unicodedata

VERSION = 'sunday-gyeonggi-20260125-v5-long-verses'
# Explicitly identified in the supplied original, not inferred from a rota.
from media_automation.people import format_people
TITLE_FONT = '경기천년제목 Bold'
SERMON_FONT = '경기천년제목V Bold'
BIBLE_FONT = 'GyeonggiTitleOTF Medium'
NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
def q(name):
    prefix, local = name.split(':'); return '{' + NS[prefix] + '}' + local

def _font(paragraph, face, points, bold=True):
    for run in paragraph.findall('a:r', NS):
        props = run.find('a:rPr', NS)
        if props is None: props = E.Element(q('a:rPr')); run.insert(0, props)
        props.set('sz', str(points * 100)); props.set('b', '1' if bold else '0')
        props.set('spc', '0'); props.set('lang', 'ko-KR')
        for tag in ('latin', 'ea', 'cs'):
            font = props.find('a:' + tag, NS)
            if font is None: font = E.SubElement(props, q('a:' + tag))
            font.set('typeface', face)

def _box(shape, bounds):
    transform = shape.find('p:spPr/a:xfrm', NS)
    for tag, keys, values in [('off', ('x','y'), bounds[:2]), ('ext', ('cx','cy'), bounds[2:])]:
        node = transform.find('a:' + tag, NS)
        for key,value in zip(keys,values): node.set(key,str(value))

def _paragraph_text(paragraph):
    return ''.join(' ' if node.tag == q('a:br') else node.text or ''
                   for node in paragraph.iter() if node.tag in (q('a:t'),q('a:br')))

def _spacing(paragraph, alignment='ctr', before=10, line_percent=100000):
    props = paragraph.find('a:pPr', NS)
    if props is None: props = E.Element(q('a:pPr')); paragraph.insert(0, props)
    props.set('algn', alignment); props.set('marL', '0'); props.set('indent', '0')
    for tag in ('lnSpc', 'spcBef', 'spcAft'):
        for node in list(props.findall('a:' + tag, NS)): props.remove(node)
    for index, (tag, child, value) in enumerate([('lnSpc','spcPct',line_percent),('spcBef','spcPts',before*100),('spcAft','spcPts',0)]):
        node=E.Element(q('a:' + tag));E.SubElement(node,q('a:' + child),val=str(value));props.insert(index,node)


def _announcement(shape, key):
    tx=shape.find('p:txBody',NS)
    paragraphs=[p for p in tx.findall('a:p',NS) if p.findall('a:r',NS)]
    values=[_paragraph_text(p).strip() for p in paragraphs]
    combined=' '.join(values)
    if '교회 소식' in key or combined.replace(' ','')=='교회소식':
        text='교  회  소  식'
    else:
        import re
        offering='봉헌기도' in key or combined.startswith('봉헌기도')
        prayer='기도' in key or combined.startswith(('기도','기 도'))
        special='특송' in key or combined.startswith('특송')
        if not (offering or prayer or special):return
        label='봉헌기도' if offering else '기 도' if prayer else '특송'
        person=re.sub(r'^(?:봉헌\s*기도|기\s*도|특송)\s*:?\s*','',combined).strip()
        # Preserve provided titles and group names; add only a confirmed person's title.
        person=format_people(person)
        text=label+(' :  ' if prayer and not offering else ' : ')+person
    p=paragraphs[0]
    for node in list(p):
        if node.tag!=q('a:pPr'):p.remove(node)
    run=E.SubElement(p,q('a:r'));E.SubElement(run,q('a:rPr'));E.SubElement(run,q('a:t')).text=text
    for node in list(tx.findall('a:p',NS)):tx.remove(node)
    tx.append(p);_spacing(p)


def _fit_verse(text):
    # Fit the final reference font, after removing the earlier soft breaks.
    # The existing body box is 540 x 351 pt; retain padding and generous leading.
    words = text.split()
    for size in (41, 34, 32, 30, 28, 26, 24):
        lines = []; line = ''
        for word in words:
            candidate = (line + ' ' + word).strip()
            width = sum(1 if unicodedata.east_asian_width(c) in ('W', 'F') else .55 for c in candidate) * size
            if line and width > 515:
                lines.append(line); line = word
            else:
                line = candidate
        if line: lines.append(line)
        leading = 55 if size == 41 else round(size * 1.45, 2)
        if len(lines) * leading <= 330:
            return size, leading, lines
    raise ValueError('성경 한 절이 화면에 들어가지 않습니다. 본문 배치를 확인하세요.')


def _scripture(root, shapes):
    reference, body = shapes
    for p in reference.findall('p:txBody/a:p',NS):
        _font(p,BIBLE_FONT,38,False);_spacing(p,'l',8)
    _box(reference, (991461,619431,8146192,671840))
    paragraphs = [p for p in body.findall('p:txBody/a:p',NS) if p.findall('a:r',NS)]
    number, *verses = paragraphs
    number_shape = deepcopy(body)
    number_shape.find('p:nvSpPr/p:cNvPr',NS).set('id',str(max(int(n.get('id')) for n in root.findall('.//p:cNvPr',NS))+1))
    number_shape.find('p:nvSpPr/p:cNvPr',NS).set('name','Verse number')
    number_tx = number_shape.find('p:txBody',NS)
    for p in list(number_tx.findall('a:p',NS)):number_tx.remove(p)
    number_tx.append(deepcopy(number));_font(number_tx.find('a:p',NS),BIBLE_FONT,41)
    _spacing(number_tx.find('a:p',NS),'r',8)
    _box(number_shape,(636462,1536763,947655,4460819))
    root.find('p:cSld/p:spTree',NS).append(number_shape)
    tx = body.find('p:txBody',NS)
    for p in list(tx.findall('a:p',NS)):tx.remove(p)
    for p in verses:
        text = _paragraph_text(p)
        size, leading, lines = _fit_verse(text)
        for node in list(p):
            if node.tag != q('a:pPr'):p.remove(node)
        for i, line in enumerate(lines):
            if i: E.SubElement(p,q('a:br'))
            run=E.SubElement(p,q('a:r'));E.SubElement(run,q('a:rPr'));E.SubElement(run,q('a:t')).text=line
        props=p.find('a:pPr',NS)
        if props is None:props=E.Element(q('a:pPr'));p.insert(0,props)
        props.set('marL','0');props.set('indent','0');props.set('algn','just')
        for spacing in list(props.findall('a:lnSpc',NS)):props.remove(spacing)
        spacing=E.Element(q('a:lnSpc'));E.SubElement(spacing,q('a:spcPts'),val=str(round(leading*100)));props.insert(0,spacing)
        _font(p,BIBLE_FONT,size);tx.append(p)
    _box(body,(1632702,1524261,6854597,4460819))

def apply_sunday_typography(path, mapping):
    path=Path(path)
    with ZipFile(path) as package:parts={info.filename:(info,package.read(info.filename)) for info in package.infolist()}
    # Only the engine's base theme/master; imported score themes remain untouched.
    for name in ('ppt/theme/theme1.xml', 'ppt/slideMasters/slideMaster1.xml', 'ppt/presentation.xml'):
        if name not in parts:continue
        info,blob=parts[name];root=E.fromstring(blob)
        if name.startswith('ppt/theme/'):
            for family in root.findall('.//a:fontScheme/a:majorFont',NS)+root.findall('.//a:fontScheme/a:minorFont',NS):
                for tag in ('latin','ea','cs'):
                    face=family.find('a:'+tag,NS)
                    if face is not None:face.set('typeface',BIBLE_FONT)
        else:
            for style in root.findall('.//p:txStyles',NS)+root.findall('p:defaultTextStyle',NS):
                for props in style.findall('.//a:defRPr',NS):
                    for tag in ('latin','ea','cs'):
                        face=props.find('a:'+tag,NS)
                        if face is None:face=E.SubElement(props,q('a:'+tag))
                        face.set('typeface',BIBLE_FONT)
        parts[name]=(info,E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True))
    changed=[]
    for entry in mapping:
        if entry.get('status') not in ('rendered','bible_inserted'):continue
        key=entry['key']
        if entry['kind']=='blank':continue
        for index in range(entry['start'],entry['end']+1):
            name=f'ppt/slides/slide{index}.xml';info,blob=parts[name];root=E.fromstring(blob)
            shapes=[sp for sp in root.findall('.//p:sp',NS) if sp.findall('.//a:t',NS)]
            if not shapes:continue
            if entry['status']=='bible_inserted':
                if len(shapes)!=2:raise ValueError('예배 성경 텍스트 구조를 확인하세요.')
                _scripture(root,shapes)
            elif key=='설교 제목':
                paras=[p for sp in shapes for p in sp.findall('p:txBody/a:p',NS) if p.findall('a:r',NS)]
                for i,p in enumerate(paras):
                    _font(p,TITLE_FONT if i==0 else SERMON_FONT,44,i!=0)
                    _spacing(p,before=8)
                    if i>0:
                        for props in p.findall('a:r/a:rPr',NS):props.set('spc','-60')
            else:
                size=48 if '봉헌기도' in key else 50
                for sp in shapes:
                    _announcement(sp,key)
                    for p in sp.findall('p:txBody/a:p',NS):_font(p,TITLE_FONT,size)
            parts[name]=(info,E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True));changed.append(index)
    temporary=path.with_suffix('.typography.tmp')
    with ZipFile(temporary,'w',ZIP_DEFLATED) as package:
        for info,blob in parts.values():package.writestr(info,blob)
    temporary.replace(path)
    return changed
