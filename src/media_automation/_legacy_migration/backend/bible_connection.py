"""Read only explicitly validated local Bible sources; never infer weekly input."""
import json
import re
import sys
from pathlib import Path
import yaml
sys.path.insert(0,'/Users/moonaneul/Documents/media-automation/src')
from media_automation.bible.json_source import build_index,lookup

SOURCES=Path('/Users/moonaneul/Documents/media-automation/data/private/bible_sources')

PROVIDED=Path('/Users/moonaneul/Documents/media-automation/data/private/bible_fixed.json')

def resolve(order, source_dir=SOURCES, provided_file=PROVIDED):
    raw=json.loads(provided_file.read_text(encoding='utf-8-sig')) if source_dir==SOURCES and provided_file.is_file() else {}
    checked={}
    for path in sorted(source_dir.glob('*.yaml')):
        source=yaml.safe_load(path.read_text())
        if source.get('translation')!='개역개정' or source.get('validated') is not True:continue
        for passage in source.get('passages',{}).values():
            from media_automation.bible.json_source import parse_reference
            book,chapter,_,_=parse_reference(passage['reference'])
            for number,text in passage['verses'].items():
                end=passage.get('verse_ends',{}).get(number,number)
                key=f'{book}{chapter}:{number}'+(f'~{end}' if end!=number else '')
                if key in checked and checked[key]!=text:raise ValueError('검수된 성경 자료가 서로 다릅니다: '+key)
                checked[key]=text
    index=build_index(raw) if raw else build_index(checked)
    checked_index=build_index(checked);result={}
    for block in order:
        if block['kind']!='input' or block.get('state')!='VALUE':continue
        if '기도' in block['key'] and '내용' in block['key']:
            lines=[];expanded=False
            for line in block['content'].splitlines():
                reference=re.sub(r'^\s*[-•·]\s*','',line.strip()).strip('()（） ')
                # Explicit addresses can accompany prose; already supplied verse text stays intact.
                matches=list(re.finditer(r'[가-힣]+\s*\d+\s*:\s*\d+(?:\s*[~～–-]\s*\d+)?',reference))
                if matches and not re.search(r'\[\d+\]',line):
                    try:
                        quotations=[]
                        for match in matches:
                            address=match.group()
                            try:part=lookup(checked_index,address)['units']
                            except KeyError:part=lookup(index,address)['units']
                            quotations.append('\n'.join('['+str(u['start_verse'])+'] '+u['text'].replace('세례','침례') for u in part)+' ('+address+')')
                        prose=reference
                        for match in reversed(matches):prose=prose[:match.start()]+prose[match.end():]
                        prose=prose.strip('()（） ,;，；')
                        lines.append((prose+'\n' if prose else '')+'\n'.join(quotations))
                        expanded=True
                        continue
                    except (ValueError,KeyError):pass
                lines.append(line)
            if expanded:result[block['key']]={'units':[],'resolved_content':'\n'.join(lines),'translation':'개역개정','text_review_pending':True}
            continue
        if not re.search('성경 본문|추가 말씀',block['key']):continue
        try:
            references=[s.strip() for s in re.split(r'[,，;；\n]',block['content']) if s.strip()]
            if not references:raise ValueError('성경 주소 없음')
            units=[]
            validated=True
            for reference in references:
                try:part=lookup(checked_index,reference)['units']
                except KeyError:
                    part=lookup(index,reference)['units'];validated=False
                units.extend([{**unit,'passage_reference':reference} for unit in part])
            result[block['key']]={'units':units,'translation':'개역개정','source_validated':validated,'source':'checked_passages' if validated else 'user_provided_bible','text_review_pending':not validated}
        except (ValueError,KeyError) as error:
            result[block['key']]={'units':[],'error':str(error)}
    return result

if __name__=='__main__':print(json.dumps(resolve(json.loads(sys.stdin.read())),ensure_ascii=False))
