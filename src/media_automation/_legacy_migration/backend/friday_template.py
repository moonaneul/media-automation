"""Edit existing Friday Zoom template elements; preserve their original parts."""
import copy,json,sys,tempfile
from pathlib import Path
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Pt, Inches
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.dml.color import RGBColor
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'friday-in-person-check'))
from attach_originals import engine
SOURCE=Path(__file__).resolve().parent.parent/'zoom-media-check/friday-full-preview-copy.pptx'

def text(shape,value,size=None):
    frame=shape.text_frame
    sample=next((p for p in frame.paragraphs if p.text.strip()),frame.paragraphs[0])
    props=copy.deepcopy(sample._p.find(qn('a:pPr')))
    style=copy.deepcopy(sample.runs[0]._r.find(qn('a:rPr'))) if sample.runs else None
    frame.clear()
    for old in list(frame.paragraphs[0]._p):
        if old.tag in (qn('a:pPr'),qn('a:endParaRPr')):frame.paragraphs[0]._p.remove(old)
    for i,line in enumerate(value.split('\n')):
        p=frame.paragraphs[0] if i==0 else frame.add_paragraph()
        if props is not None:
            clean=copy.deepcopy(props)
            if clean.get('algn') in ('dist','thaiDist','just','justLow'):clean.set('algn','l')
            p._p.insert(0,clean)
        run=p.add_run();run.text=line
        if style is not None:
            clean=copy.deepcopy(style);clean.set('spc','0');run._r.insert(0,clean)
        if size:run.font.size=Pt(size)

def build(args):
    service=args['service'];ordinary=service in ('wednesday','sunday');zoom=args['zoom'];source=SOURCE if zoom else Path(__file__).with_name('static')/'friday-in-person-reference.pptx'
    if ordinary:source=Path(__file__).with_name('static')/(service+'-reference.pptx')
    title_template=41 if service=='wednesday' else 88 if service=='sunday' else 12 if zoom else 82
    bible_template=39 if service=='wednesday' else 89 if service=='sunday' else 7 if zoom else 59
    center_template=28 if service=='wednesday' else 63 if service=='sunday' else 82
    target=Path(args['output']);base=Presentation(source)
    for node in list(base.slides._sldIdLst):base.part.drop_rel(node.rId);base.slides._sldIdLst.remove(node)
    base.save(target);mapping=[];unresolved=[];date=args['date'].replace('-','.')
    with tempfile.TemporaryDirectory(dir=target.parent) as folder:
        folder=Path(folder)
        def append(template,values):
            part=folder/'part.pptx';blank=Presentation(target)
            for node in list(blank.slides._sldIdLst):blank.part.drop_rel(node.rId);blank.slides._sldIdLst.remove(node)
            blank.save(part)
            engine.OpenXmlSlideMerger().insert_range(part,source,after_slide=0,start_slide=template,end_slide=template)
            deck=Presentation(part);slide=deck.slides[0]
            # Animation states referring to cleared weekly text must not hide new text.
            for timing in list(slide._element.findall(qn('p:timing'))):slide._element.remove(timing)
            for i,shape in enumerate(slide.shapes):
                if shape.has_text_frame:
                    if (not zoom and template in (1,2,3,4)) or (zoom and template==18):continue
                    if zoom and template==1 and i==0:
                        for leaf in shape._element.iter(qn('a:t')):
                            if leaf.text:leaf.text=leaf.text.replace('2026.09.11',date)
                        continue
                    value,size=values.get(i,('',None));text(shape,value,size)
            if template==title_template:
                frame=slide.shapes[0].text_frame;frame.vertical_anchor=MSO_ANCHOR.MIDDLE
                for i,paragraph in enumerate(frame.paragraphs):
                    paragraph.alignment=PP_ALIGN.CENTER
                    for run in paragraph.runs:
                        run.font.size=Pt(40 if i==0 else 28)
                        run.font.bold=i==0
            if zoom and template==15:
                shape=slide.shapes[3];shape.width=Inches(11.2);shape.top=Inches(1.65);shape.height=Inches(4.9);shape.text_frame.word_wrap=True
                for i,paragraph in enumerate(shape.text_frame.paragraphs):
                    paragraph.line_spacing=1.25
                    paragraph.alignment=PP_ALIGN.LEFT
                    if i==0:
                        for run in paragraph.runs:run.font.size=Pt(32);run.font.bold=True
            if zoom and template==7:
                for i,paragraph in enumerate(slide.shapes[2].text_frame.paragraphs):
                    if i>=3:
                        paragraph.alignment=PP_ALIGN.LEFT
                        for run in paragraph.runs:run.font.bold=True
            if not zoom and template==center_template:
                shape=slide.shapes[0];shape.top=Inches(1.5);shape.height=Inches(4.5);shape.text_frame.vertical_anchor=MSO_ANCHOR.MIDDLE
                for i,paragraph in enumerate(shape.text_frame.paragraphs):
                    paragraph.alignment=PP_ALIGN.CENTER;paragraph.line_spacing=1.45
                    if i==0:
                        for run in paragraph.runs:run.font.size=Pt(40);run.font.bold=True
            if ordinary and template==bible_template:
                for paragraph in slide.shapes[3].text_frame.paragraphs:paragraph.alignment=PP_ALIGN.LEFT;paragraph.line_spacing=1.45
            if not zoom and not ordinary and template==59:
                for paragraph in slide.shapes[5].text_frame.paragraphs:
                    paragraph.alignment=PP_ALIGN.LEFT;paragraph.line_spacing=1.45
                    for run in paragraph.runs:run.font.bold=True
                for i in (0,1,5):
                    for paragraph in slide.shapes[i].text_frame.paragraphs:
                        for run in paragraph.runs:run.font.color.rgb=RGBColor(0,0,0)
            # These are poster icons from removed historical audio, not this week's media.
            if zoom and template in (15,18):
                for shape in list(slide.shapes):
                    if shape._element.tag==qn('p:pic') and shape.name.startswith('기도 '):slide.shapes._spTree.remove(shape._element)
            deck.save(part);count=len(Presentation(target).slides)
            engine.OpenXmlSlideMerger().insert_all(target,part,after_slide=count)
            return count+1
        if zoom:append(1,{0:(date+'\n금요기도회\n지금은 기도로 예배를 준비하는 시간입니다',None)})
        else:
            for number in range(1,5):
                original=Presentation(source).slides[number-1]
                append(number,{i:(sh.text,None) for i,sh in enumerate(original.shapes) if sh.has_text_frame})
        mapping.append({'key':'예배 준비','kind':'pre_service','start':1,'end':1 if zoom else 4,'status':'original_inserted'})
        order=args['order'];skip=set()
        for index,block in enumerate(order):
            if index in skip:continue
            key=block['key'];kind=block['kind'];value=args['bible'].get(key,{}).get('resolved_content',block.get('content') or '')
            # Preserve quotation content while starting every new verse on its own line.
            import re
            value=re.sub(r'(?<!\n)\s*(\[\d+(?:[~–-]\d+)?\])',r'\n\1',value).lstrip('\n')
            if kind=='input' and block.get('state')!='VALUE':
                if block.get('state')=='UNSET':unresolved.append(key)
                continue
            start=len(Presentation(target).slides)+1;status='rendered'
            brand={1:('하늘빛기쁨\n'+date+'\n금요기도회',None)}
            passage=args['bible'].get(key)
            if passage and passage.get('units'):
                for unit in passage['units']:
                    verse='['+str(unit['start_verse'])+'] '+unit['text'].replace('세례','침례')
                    if zoom:append(7,{**brand,2:(unit.get('passage_reference',value)+'\n____________________________\n\n'+verse,28)})
                    else:append(bible_template,{0:(unit.get('passage_reference',value),28),1:('',None),3 if ordinary else 5:(verse,32)})
                status='bible_inserted'
            elif kind=='song':append(6 if zoom else 5,{});status='missing_song_asset';unresolved.append(key+(':media_asset' if zoom else ':score_asset'))
            elif kind=='blank':append(6 if zoom else 5,{})
            elif '성경 본문' in key or '추가 말씀' in key:
                append(6 if zoom else 5,{});status='missing_verified_bible_text';unresolved.append(key+':bible_text')
            elif '설교 제목' in key:append(title_template,{0:(value+('\n'+block['subtitle'] if block.get('subtitle') else ''),32)})
            elif '개인 기도' in key:append(18,{})
            elif '기도' in key:
                body_index=index+1
                if body_index<len(order) and order[body_index]['kind']=='blank':body_index+=1
                if ' 제목 ' in key and body_index<len(order) and order[body_index]['key']==key.replace(' 제목 ',' 내용 '):
                    body=order[body_index];skip.update(range(index+1,body_index+1))
                    if body.get('state')=='VALUE':
                        body_content=args['bible'].get(body['key'],{}).get('resolved_content',body['content'])
                        citation=re.sub(r'(?<!\n)\s*(\[\d+(?:[~–-]\d+)?\])',r'\n\1',body_content).lstrip('\n')
                        citation=re.sub(r'(^|\n)\s*-\s*\n(?=\[)',r'\1',citation)
                        value+='\n\n'+citation
                if zoom:append(15,{**brand,3:(value,24 if len(value)>200 else 26)})
                else:append(center_template,{0:(value,34 if ordinary else 32)})
            else:append(12 if zoom else center_template,{0:(value,34 if ordinary else 32)})
            mapping.append({'key':key,'kind':kind,'start':start,'end':len(Presentation(target).slides),'status':status})
        if zoom and not any('개인 기도' in m['key'] for m in mapping):
            start=append(18,{})
            mapping.append({'key':'개인 기도','kind':'input','start':start,'end':start,'status':'original_inserted'})
    result={'slide_count':len(Presentation(target).slides),'mapping':mapping,'unresolved':unresolved,'complete':False,'visual_review_pending':True,'template':'existing_'+service if ordinary else 'existing_friday_zoom' if zoom else 'existing_friday_in_person'}
    Path(args['report']).write_text(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':build(json.loads(Path(sys.argv[1]).read_text()))
