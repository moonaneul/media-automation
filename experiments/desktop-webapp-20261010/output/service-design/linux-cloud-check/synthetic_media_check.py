"""Synthetic CI fixture; contains no church source content."""
from pathlib import Path
import base64
import subprocess
import zipfile
import time
from lxml import etree as E

ROOT = Path('/tmp/media-check')
for name in ('input', 'ppt', 'pdf'):
    (ROOT / name).mkdir(parents=True, exist_ok=True)

def run(*args):
    subprocess.run(args, check=True, timeout=90)

# Neutral staff-and-notes graphic, not a hymn or replacement worship score.
svg = '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="200"><rect width="800" height="200" fill="white"/>'
svg += ''.join(f'<path d="M30 {y}H770" stroke="black" stroke-width="3"/>' for y in (50,70,90,110,130))
svg += ''.join(f'<ellipse cx="{x}" cy="{y}" rx="13" ry="9"/><path d="M{x+12} {y}v-55" stroke="black" stroke-width="3"/>' for x,y in ((160,110),(330,90),(500,70)))
svg += '</svg>'
(ROOT/'input/score.svg').write_text(svg)
from PIL import Image, ImageDraw
score=Image.new('RGB',(800,200),'white')
draw=ImageDraw.Draw(score)
for y in (50,70,90,110,130): draw.line((30,y,770,y),fill='black',width=3)
for x,y in ((160,110),(330,90),(500,70)):
    draw.ellipse((x-13,y-9,x+13,y+9),fill='black')
    draw.line((x+12,y,x+12,y-55),fill='black',width=3)
score.save(ROOT/'input/score.png')
image = base64.b64encode((ROOT/'input/score.png').read_bytes()).decode()
fodp = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.presentation">
<office:automatic-styles><style:style style:name="text" style:family="paragraph"><style:text-properties style:font-name="NanumGothic" fo:font-family="NanumGothic" style:font-family-asian="NanumGothic" fo:font-size="24pt" style:font-size-asian="24pt"/></style:style></office:automatic-styles>
<office:body><office:presentation><draw:page draw:name="Synthetic check">
<draw:frame svg:x="2cm" svg:y="1cm" svg:width="24cm" svg:height="3cm"><draw:text-box><text:p text:style-name="text">한글 미리보기 확인 223장</text:p></draw:text-box></draw:frame>
<draw:frame svg:x="2cm" svg:y="5cm" svg:width="24cm" svg:height="6cm"><draw:image draw:mime-type="image/png"><office:binary-data>{image}</office:binary-data></draw:image></draw:frame>
</draw:page></office:presentation></office:body></office:document>'''
(ROOT/'input/check.fodp').write_text(fodp)
run('libreoffice','-env:UserInstallation=file:///tmp/lo-create','--headless','--convert-to','pptx','--outdir',str(ROOT/'ppt'),str(ROOT/'input/check.fodp'))
base = ROOT/'ppt/check.pptx'
assert base.is_file() and base.stat().st_size
run('ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=10','-t','2','-an','-c:v','libx264','-pix_fmt','yuv420p',str(ROOT/'input/test.mp4'))
run('ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=2','-c:a','libmp3lame',str(ROOT/'input/test.mp3'))

# Insert actual internal media relationships into a diagnostic copy of the generated slide.
P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
with zipfile.ZipFile(base) as z:
    parts={n:z.read(n) for n in z.namelist()}
assert any(n.startswith('ppt/media/') for n in parts), 'Score image was not embedded'
slide=E.fromstring(parts['ppt/slides/slide1.xml'])
rels=E.fromstring(parts['ppt/slides/_rels/slide1.xml.rels'])
tree=slide.find(f'{{{P}}}cSld/{{{P}}}spTree')
maxid=max(int(n.get('id')) for n in slide.iter(f'{{{P}}}cNvPr'))
for offset, kind, ext in ((1,'video','mp4'),(2,'audio','mp3')):
    rid='rIdDiagnostic'+kind.title()
    E.SubElement(rels,f'{{{REL}}}Relationship',Id=rid,Type=f'{R}/{kind}',Target=f'../media/test.{ext}')
    # Media frame references are internal; only structural portability is checked here.
    pic=E.fromstring(f'''<p:pic xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:nvPicPr><p:cNvPr id="{maxid+offset}" name="Synthetic {kind}"/><p:cNvPicPr/><p:nvPr><a:{kind}File r:link="{rid}"/></p:nvPr></p:nvPicPr><p:blipFill><a:blip/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1" cy="1"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>''')
    tree.append(pic)
    parts[f'ppt/media/test.{ext}']=(ROOT/f'input/test.{ext}').read_bytes()
types=E.fromstring(parts['[Content_Types].xml'])
for ext,typ in [('mp4','video/mp4'),('mp3','audio/mpeg')]:
    if not any(n.get('Extension')==ext for n in types):
        E.SubElement(types,f'{{{CT}}}Default',Extension=ext,ContentType=typ)
for path, node in [('ppt/slides/slide1.xml',slide),('ppt/slides/_rels/slide1.xml.rels',rels),('[Content_Types].xml',types)]:
    parts[path]=E.tostring(node,xml_declaration=True,encoding='UTF-8')
media=ROOT/'ppt/media-check.pptx'
with zipfile.ZipFile(media,'w',zipfile.ZIP_DEFLATED) as z:
    for name,data in parts.items(): z.writestr(name,data)
with zipfile.ZipFile(media) as z:
    assert z.testzip() is None
    for ext in ('mp4','mp3'):
        assert z.read(f'ppt/media/test.{ext}') == (ROOT/f'input/test.{ext}').read_bytes()
for path in ('test.mp4','test.mp3'):
    run('ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1',str(ROOT/'input'/path))
print('PASS: score image, internal MP4/MP3 links, exact embedded bytes and media decoding metadata')
# Preview-only copy: retain image/text; the downloadable PPT keeps both media files.
for pic in list(tree.findall(f'{{{P}}}pic')):
    if pic.find(f'.//{{{A}}}videoFile') is not None or pic.find(f'.//{{{A}}}audioFile') is not None:
        tree.remove(pic)
for rel in list(rels):
    if rel.get('Id','').startswith('rIdDiagnostic'): rels.remove(rel)
parts['ppt/slides/slide1.xml']=E.tostring(slide,xml_declaration=True,encoding='UTF-8')
parts['ppt/slides/_rels/slide1.xml.rels']=E.tostring(rels,xml_declaration=True,encoding='UTF-8')
preview=ROOT/'ppt/preview-copy.pptx'
with zipfile.ZipFile(preview,'w',zipfile.ZIP_DEFLATED) as z:
    for name,data in parts.items():
        if name not in ('ppt/media/test.mp4','ppt/media/test.mp3'): z.writestr(name,data)
with zipfile.ZipFile(media) as z:
    assert all(z.read(f'ppt/media/test.{ext}') for ext in ('mp4','mp3'))
with zipfile.ZipFile(preview) as z:
    assert z.testzip() is None
    assert not any(n.endswith(('.mp4','.mp3')) for n in z.namelist())
start=time.monotonic()
run('libreoffice','-env:UserInstallation=file:///tmp/lo-preview','--headless','--convert-to','pdf','--outdir',str(ROOT/'pdf'),str(preview))
print(f'PREVIEW_SECONDS={time.monotonic()-start:.3f}')
pdf=ROOT/'pdf/preview-copy.pdf'
assert pdf.is_file() and pdf.stat().st_size
run('pdftotext',str(pdf),str(ROOT/'text.txt'))
assert '한글미리보기확인223장' in ''.join((ROOT/'text.txt').read_text().split())
run('pdftoppm','-f','1','-singlefile','-scale-to','1000','-png',str(pdf),str(ROOT/'preview'))
from PIL import Image
im=Image.open(ROOT/'preview.png').convert('RGB')
w,h=im.size
# Staff image must survive in lower central image area, separate from title text.
crop=im.crop((int(w*.1),int(h*.35),int(w*.9),int(h*.8)))
dark=sum(1 for pixel in crop.getdata() if max(pixel)<100)
assert dark > 500, f'Score image has insufficient visible dark pixels: {dark}'
print(f'PASS: Korean text preserved and staff image visible ({dark} dark pixels)')
print('NOT CHECKED: PowerPoint playback, autoplay, actual church template fidelity')
