import base64
import binascii
from io import BytesIO
from PIL import Image, UnidentifiedImageError
import pytest
from media_automation.bulletin.cover_photo import fitted_photo,photo_bytes

def fixture_photo():
    out=BytesIO();Image.new('RGB',(1200,800),(50,120,80)).save(out,format='PNG')
    return dict(filename='test.png',data='data:image/png;base64,'+base64.b64encode(out.getvalue()).decode())

def test_cover_photo_fills_original_region_with_white_fades():
    image=Image.open(BytesIO(fitted_photo(fixture_photo())))
    assert image.size==(1015,743)
    assert image.getpixel((500,0))==(255,255,255)
    assert image.getpixel((500,742))==(255,255,255)
    assert image.getpixel((500,350))==(50,120,80)

@pytest.mark.parametrize('photo',[{},dict(filename='x',data='https://example.org/x.png'),dict(filename='x',data='data:image/png;base64,not-image')])
def test_invalid_photo_rejected(photo):
    with pytest.raises((ValueError,binascii.Error,UnidentifiedImageError)):photo_bytes(photo)


def test_pdf_photo_changes_only_original_photo_region_and_preserves_settings(tmp_path):
    import json
    from pathlib import Path
    import pymupdf
    from media_automation.web.original.work_store import WorkStore
    from media_automation.web.original.bulletin_generation import generate_bulletin
    from media_automation.web.original.generation import ROOT
    store=WorkStore(tmp_path/'work.db')
    fields={k:dict(state='VALUE',value=v) for k,v in [('설교 제목','사진 검증'),('성경 본문','단 1:8~9')]}
    store.save('2026-10-11','sunday',0,dict(fields=fields))
    request=dict(date='2026-10-11',service='sunday',revision=1)
    before=generate_bulletin(store,request)
    settings=json.loads((ROOT/'src/media_automation/web/original/bulletin-base-reference.json').read_text())
    settings['cover_photo']=fixture_photo()
    with store.connect() as db:
        db.execute('INSERT OR REPLACE INTO bulletin_settings VALUES (1,1,?)',(json.dumps(settings),))
    after=generate_bulletin(store,request)
    folder=Path(store.path).with_suffix('.generated')
    a=pymupdf.open(folder/(before['file_id']+'.pdf'));b=pymupdf.open(folder/(after['file_id']+'.pdf'))
    pa=a[0].get_pixmap();pb=b[0].get_pixmap()
    for pix in (pa,pb):
        assert all(pix.pixel(x,y)==(255,255,255) for x in range(833,pix.width) for y in range(pix.height))
    assert pa.pixel(630,330)!=pb.pixel(630,330)
    assert pb.pixel(630,530)==(255,255,255) # old lake removed even behind footer
    # The footer's dark lettering remains at the same positions, while its
    # photographic background is removed rather than copied underneath it.
    dark=[(x,y) for y in range(475,550) for x in range(450,810) if max(pa.pixel(x,y))<50]
    assert len(dark)>300
    assert sum(any(max(pb.pixel(x+dx,y+dy))<100 for dx in (-1,0,1) for dy in (-1,0,1)) for x,y in dark)/len(dark)>.99
    assert a[1].get_pixmap().samples==b[1].get_pixmap().samples
    assert store.get('2026-10-11','sunday')['data']['fields']==fields
