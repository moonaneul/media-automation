"""Font families from 2026-09-18 Zoom and 2026-08-28 in-person originals.
Only generated text changes; imported songs, media and layouts are preserved.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
from .sunday_typography import NS, q

VERSION = 'friday-original-layout-readable-centered-v8-prayer-fit'

def apply_friday_typography(path, mapping, *, zoom):
    path = Path(path)
    with ZipFile(path) as package:
        parts = {i.filename: (i, package.read(i.filename)) for i in package.infolist()}
    changed = []
    for entry in mapping:
        if entry.get('status') not in ('rendered', 'bible_inserted') or entry['kind'] == 'blank':
            continue
        for index in range(entry['start'], entry['end'] + 1):
            name = f'ppt/slides/slide{index}.xml'
            info, blob = parts[name]
            root = E.fromstring(blob)
            shapes = [s for s in root.findall('.//p:sp', NS) if s.findall('.//a:t', NS)]
            for shape_index, shape in enumerate(shapes):
                if zoom:
                    if entry['status'] == 'bible_inserted':
                        face = '나눔스퀘어 Bold'
                    elif entry['key'] == '설교 제목':
                        face = '나눔바른고딕 UltraLight'
                    elif '개인 기도' in entry['key']:
                        face = '나눔스퀘어라운드 Bold'
                    elif '기도' in entry['key']:
                        face = '나눔스퀘어라운드 ExtraBold'
                    else:
                        face = '나눔스퀘어라운드 Bold'
                else:
                    face = 'GyeonggiTitleOTF Medium' if entry['status'] == 'bible_inserted' else '경기천년제목 Bold'
                # Reference typography is role-specific, including size and weight.
                paragraphs = shape.findall('.//a:p', NS)
                for paragraph_index, paragraph in enumerate(paragraphs):
                    if not zoom and '기도' in entry['key'] and '개인 기도' not in entry['key']:
                        ppr = paragraph.find('a:pPr', NS)
                        if ppr is None:
                            ppr = E.Element(q('a:pPr')); paragraph.insert(0, ppr)
                        ppr.set('algn', 'l')
                    if zoom:
                        ppr = paragraph.find('a:pPr', NS)
                        if ppr is None:
                            ppr = E.Element(q('a:pPr')); paragraph.insert(0, ppr)
                        if '기도' in entry['key'] and '개인 기도' not in entry['key']:
                            spacing = ppr.find('a:lnSpc', NS)
                            if spacing is not None: ppr.remove(spacing)
                            spacing = E.SubElement(ppr, q('a:lnSpc'))
                            E.SubElement(spacing, q('a:spcPct')).set('val', '100000')
                for run in shape.findall('.//a:r', NS):
                    props = run.find('a:rPr', NS)
                    if props is None:
                        props = E.Element(q('a:rPr')); run.insert(0, props)
                    if zoom:
                        paragraph_index = paragraphs.index(run.getparent())
                        if entry['status'] == 'bible_inserted':
                            size = 1800 if props.get('baseline') else 3200
                        elif entry['key'] == '설교 제목':
                            size = 4400 if shape_index == 0 and paragraph_index == 0 else 3200
                        elif '개인 기도' in entry['key']:
                            size = 3000 if shape.get('name') == '개인 기도 보조 안내' or shape_index > 0 else 4800
                        elif '기도' in entry['key']:
                            size = 3600 if paragraph_index == 0 else 3200
                            props.set('spc', '-150')
                            if paragraph_index > 0:
                                face = '나눔스퀘어 Bold' if '첫 기도' in entry['key'] else '나눔스퀘어 Light'
                            else:
                                face = '나눔스퀘어라운드 ExtraBold'
                        else:
                            size = None
                        if size is not None:
                            props.set('sz', str(size)); props.set('b', '1')
                    for tag in ('latin', 'ea', 'cs'):
                        font = props.find('a:' + tag, NS)
                        if font is None: font = E.SubElement(props, q('a:' + tag))
                        font.set('typeface', face)
            parts[name] = info, E.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
            changed.append(index)
    temporary = path.with_suffix('.fonts.tmp')
    with ZipFile(temporary, 'w', ZIP_DEFLATED) as package:
        for info, blob in parts.values(): package.writestr(info, blob)
    temporary.replace(path)
    return changed
