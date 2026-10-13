"""Use explicit weekly values; person metadata must never become standalone slides."""
import re
from media_automation.input_text import clean_leading_marks
def build_order(groups,fields,service=None):
    if not isinstance(groups,list) or not isinstance(fields,dict):raise ValueError('Invalid form order')
    # Normalize older clients that still send Wednesday ads at the end.
    if service in ('wednesday','sunday'):
        groups=[[name,[label for label in labels if label!='광고 순서']] for name,labels in groups]
        for _,labels in groups:
            prayer='기도 담당자' if service=='wednesday' else '2부 기도 담당자'
            if prayer in labels:
                labels.insert(labels.index(prayer)+1,'광고 순서')
                break
    order=[];seen=set();prayer_number=0;after_sermon=False
    for group in groups:
        if not isinstance(group,list) or len(group)!=2 or not isinstance(group[1],list):raise ValueError('Invalid order group')
        if group[0].startswith(('주보','이번 주 주보','전달 주보','목장','이번 주 섬김','다음 주 섬김','주보 예배','다음 주 섬김')):continue
        for label in group[1]:
            if not isinstance(label,str) or label in seen:raise ValueError('Duplicate or invalid form field')
            seen.add(label)
            if label=='설교 제목' and not after_sermon:
                after_sermon=True;prayer_number=0
            if service=='sunday' and label=='교회 소식':continue
            if label.startswith('1부') or label in ('주일 인도자','찬양 인도자','2부 찬양 인도자','폐회 기도 담당자','전달 주보 찬양 목록','전달 섬김표 원문','표지 변경 사항'):continue
            f={'state':'VALUE','value':'광고' if service=='wednesday' else '교회 소식'} if label=='광고 순서' and service in ('wednesday','sunday') else fields.get(label,{'state':'UNSET','value':''});state=f.get('state');text=f.get('value','')
            if isinstance(text,str):text=re.sub(r'_x000[bB]_','\n',text).replace('\v','\n')
            if state not in ('VALUE','NONE','UNSET') or not isinstance(text,str):raise ValueError('Invalid input state')
            if state=='NONE':continue
            if state=='VALUE':
                text=clean_leading_marks(text)
                if '담당자' in label and re.sub(r'\s','',text) in ('설거지','기도','봉헌기도','수요예배기도','1부','2부','이번주','다음주'):
                    raise ValueError(label+'에 표의 제목이 들어갔습니다. 담당자 이름을 확인하세요.')
            song=any(t in label for t in ('찬양','찬송','특송')) and not ('관련' in label or '기도' in label and label!='기도 후 찬양')
            if not song and state=='UNSET':
                order.append({'kind':'input','key':label,'state':state,'content':''});continue
            previous=next((b for b in reversed(order) if b['kind']!='blank' and b.get('state')!='UNSET'),None)
            same_prayer=service=='friday' and previous and '기도' in label and (' 제목 ' in label or ' 내용 ' in label) and previous.get('group')==group[0] and '기도' in previous['key']
            if order and not same_prayer:order.append({'kind':'blank','key':'boundary:'+label})
            block={'kind':'song' if song else 'input','key':label,'state':state,'content':text if state=='VALUE' else None,'group':group[0]}
            if not song:
                if '기도 제목' in label and state=='VALUE' and text.strip():
                    prayer_number+=1
                    title=clean_leading_marks(re.sub(r'^\s*(?:\(\d+\)|\d+\s*[.)번:]|\d+\s+|[①-⑳])\s*','',text).strip())
                    block['content']=str(prayer_number)+'. '+title
                elif label in ('기도 담당자','2부 기도 담당자'):block['content']='기도\n'+text
                elif label=='2부 봉헌기도 담당자':block['content']='봉헌기도\n'+text
                elif label in ('교회 소식','광고 순서'):block['content']='교회 소식' if service=='sunday' else '광고'
                elif label=='설교 제목':
                    reference=fields.get('성경 본문',{})
                    block['subtitle']=clean_leading_marks(reference.get('value','')) if reference.get('state')=='VALUE' else ''
            order.append(block)
    return order


def combine_friday_prayers(order, bible, *, include_personal=True):
    """Keep each explicit prayer title and its quotation on the same screen."""
    result=[];index=0
    while index<len(order):
        block=dict(order[index]);index+=1
        if ' 제목 ' in block['key'] and '기도' in block['key']:
            next_index=index
            if next_index<len(order) and order[next_index]['kind']=='blank':next_index+=1
            if next_index<len(order) and order[next_index]['key']==block['key'].replace(' 제목 ',' 내용 '):
                body=order[next_index]
                if body.get('state')=='VALUE':
                    content=bible.get(body['key'],{}).get('resolved_content',body['content'])
                    block['content']=(block.get('content') or '')+'\n\n'+content
                    block['supporting_key']=body['key']
                    block['supporting_review_pending']=bible.get(body['key'],{}).get('text_review_pending',False)
                index=next_index+1
        result.append(block)
    if include_personal and not any('개인 기도' in b['key'] for b in result):
        result.append(dict(kind='input',key='개인 기도',state='VALUE',content='지금은 개인 기도 시간입니다.\n더 깊은 주님과의 친밀함 가운데 나아가시기 바랍니다.',group='공동체·중보 기도'))
    # Older forms store an entire numbered prayer section in one textarea.
    # Keep its supporting lines with the topic, but give every topic its own slide.
    separated=[]
    for block in result:
        text=block.get('content') or ''
        matches=list(re.finditer(r'^\s*\d+[.)]\s+\S.*$',text,re.M))
        if block['kind']=='input' and '기도' in block['key'] and len(matches)>1:
            prefix=text[:matches[0].start()].strip()
            if prefix:
                separated.append(dict(block,content=prefix))
            for i,match in enumerate(matches):
                end=matches[i+1].start() if i+1<len(matches) else len(text)
                separated.append(dict(block,key=block['key']+' · '+str(i+1),content=text[match.start():end].strip()))
        else:
            separated.append(block)
    return separated
