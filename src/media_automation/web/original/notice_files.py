"""Read documents with table coordinates; never assign flattened merged cells."""
from pathlib import Path
import struct
import tempfile
import zipfile
import zlib
from xml.etree import ElementTree as ET
from media_automation.bulletin.hwp import (
    extract_hwp_text, _iter_hwp_records, _decode_para_text, _is_compressed,
)


def hwp_tables(path):
    import olefile
    tables = []
    with olefile.OleFileIO(str(path)) as ole:
        compressed = _is_compressed(ole.openstream('FileHeader').read())
        sections = sorted((p for p in ole.listdir() if p[0] == 'BodyText'),
                          key=lambda p: int(p[-1].replace('Section', '')))
        for section in sections:
            raw = ole.openstream(section).read()
            records = list(_iter_hwp_records(zlib.decompress(raw, -15) if compressed else raw))
            table = cell = None
            table_level = None
            for tag, level, payload in records:
                if table is not None and level < table_level:
                    table = cell = None
                if tag == 77 and len(payload) >= 8:
                    rows, columns = struct.unpack_from('<HH', payload, 4)
                    table = {'rows': rows, 'columns': columns, 'cells': []}
                    table_level = level
                    tables.append(table)
                    cell = None
                elif tag == 72 and table is not None and level == table_level and len(payload) >= 30:
                    column, row, colspan, rowspan = struct.unpack_from('<HHHH', payload, 8)
                    if (row + rowspan > table['rows'] or column + colspan > table['columns']
                            or not rowspan or not colspan):
                        raise ValueError('HWP 표 좌표가 잘못되었습니다.')
                    cell = dict(row=row, column=column, rowspan=rowspan, colspan=colspan, text='')
                    table['cells'].append(cell)
                elif tag == 67 and cell is not None and level > table_level:
                    text = _decode_para_text(payload).strip()
                    if text:
                        cell['text'] += ('\n' if cell['text'] else '') + text
    return tables


def hwpx_document(path):
    paragraphs, tables = [], []
    def local(tag): return tag.rsplit('}', 1)[-1]
    def text(node): return ''.join(n.text or '' for n in node.iter() if local(n.tag) == 't')
    with zipfile.ZipFile(path) as archive:
        for name in sorted(n for n in archive.namelist() if n.startswith('Contents/section') and n.endswith('.xml')):
            if archive.getinfo(name).file_size > 8 * 1024 * 1024:
                raise ValueError('HWPX 압축 해제 크기를 초과했습니다.')
            root = ET.fromstring(archive.read(name))
            for p in root.iter():
                if local(p.tag) == 'p':
                    value = text(p).strip()
                    if value: paragraphs.append(value)
                if local(p.tag) != 'tbl': continue
                table = {'rows': int(p.get('rowCnt', '0')), 'columns': int(p.get('colCnt', '0')), 'cells': []}
                for tc in p.iter():
                    if local(tc.tag) != 'tc': continue
                    children = {local(n.tag): n for n in tc}
                    address, span = children.get('cellAddr'), children.get('cellSpan')
                    if address is None or span is None: continue
                    table['cells'].append(dict(row=int(address.get('rowAddr')), column=int(address.get('colAddr')),
                        rowspan=int(span.get('rowSpan')), colspan=int(span.get('colSpan')), text=text(tc).strip()))
                tables.append(table)
    return '\n'.join(paragraphs), tables


def extract_notice(filename, content):
    suffix = Path(filename).suffix.lower()
    if suffix not in ('.hwp', '.hwpx') or not 0 < len(content) <= 8 * 1024 * 1024:
        raise ValueError('지원 파일과 크기를 확인하세요.')
    with tempfile.TemporaryDirectory(prefix='media-notice-') as directory:
        path = Path(directory) / ('notice' + suffix)
        path.write_bytes(content)
        if suffix == '.hwpx': text, tables = hwpx_document(path)
        else: text, tables = extract_hwp_text(path), hwp_tables(path)
    if not text.strip() or len(text) > 1024 * 1024:
        raise ValueError('파일을 읽지 못했습니다.')
    return {'text': text, 'tables': tables, 'filename': filename}
