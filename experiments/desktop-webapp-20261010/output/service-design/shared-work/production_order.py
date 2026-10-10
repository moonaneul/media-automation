"""Use explicit weekly values; person metadata must never become standalone slides."""
import re
def build_order(groups,fields,service=None):
    if not isinstance(groups,list) or not isinstance(fields,dict):raise ValueError('Invalid form order')
    # Normalize older clients that still send Wednesday ads at the end.
    if service=='wednesday':
        groups=[[name,[label for label in labels if label!='광고 순서']] for name,labels in groups]
        for _,labels in groups:
            if '기도 담당자' in labels:
                labels.insert(labels.index('기도 담당자')+1,'광고 순서')
                break
    order=[];seen=set();prayer_number=0;after_sermon=False
    for group in groups:
        if not isinstance(group,list) or len(group)!=2 or not isinstance(group[1],list):raise ValueError('Invalid order group')
        if group[0].startswith(('주보','이번 주 주보','전달 주보','목장','이번 주 섬김','다음 주 섬김')):continue
        for label in group[1]:
            if not isinstance(label,str) or label in seen:raise ValueError('Duplicate or invalid form field')
            seen.add(label)
            if label=='설교 제목' and not after_sermon:
                after_sermon=True;prayer_number=0
            if label.startswith('1부') or label in ('주일 인도자','찬양 인도자','2부 찬양 인도자','폐회 기도 담당자','전달 주보 찬양 목록','전달 섬김표 원문','표지 변경 사항'):continue
            f=fields.get(label,{'state':'UNSET','value':''});state=f.get('state');text=f.get('value','')
            if isinstance(text,str):text=re.sub(r'_x000[bB]_','\n',text).replace('\v','\n')
            if state not in ('VALUE','NONE','UNSET') or not isinstance(text,str):raise ValueError('Invalid input state')
            if state=='NONE':continue
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
                    title=re.sub(r'^\s*(?:\(\d+\)|\d+\s*[.)번:]|\d+\s+|[①-⑳])\s*','',text).strip()
                    block['content']=str(prayer_number)+'. '+title
                elif label in ('기도 담당자','2부 기도 담당자'):block['content']='기도\n'+text
                elif label=='2부 봉헌기도 담당자':block['content']='봉헌기도\n'+text
                elif label in ('교회 소식','광고 순서'):block['content']='광고'
                elif label=='설교 제목':
                    reference=fields.get('성경 본문',{})
                    block['subtitle']=reference.get('value','') if reference.get('state')=='VALUE' else ''
            order.append(block)
    return order
