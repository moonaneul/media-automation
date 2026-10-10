"""Friday in-person planning prototype. No source deck or prior week is consulted."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlanResult:
    blocks: list[dict[str, Any]]
    unresolved: list[str]

    @property
    def ready(self):
        return not self.unresolved


def value(field, key, unresolved):
    state=field.get('state')
    if state not in ('UNSET','NONE','VALUE'):
        raise ValueError(f'{key}: invalid field state')
    if state=='UNSET':
        unresolved.append(key)
        return None
    if state=='NONE':
        return None
    result=field.get('value')
    if result is None or isinstance(result,str) and not result.strip():
        raise ValueError(f'{key}: VALUE must contain an explicit value')
    return result


def build_plan(data):
    if data.get('mode')!='in_person':
        raise ValueError('Friday mode must explicitly be in_person')
    unresolved=[]
    value(data['date'],'date',unresolved)
    if data['date']['state']=='NONE':
        raise ValueError('An explicit service date is required')
    blocks=[]
    keys=set()
    for item in data['order']:
        key=item['key']
        if key in keys: raise ValueError(f'Duplicate order key: {key}')
        keys.add(key)
        kind=item['kind']
        if kind not in ('song','sermon_title','scripture','prayer_topics'):
            raise ValueError(f'Unsupported Friday block: {kind}')
        content=value(item['content'],key,unresolved)
        if item['content']['state']=='NONE':
            continue
        if kind=='prayer_topics' and content is not None:
            if not isinstance(content,list) or not content:
                raise ValueError('Prayer topics require a nonempty list')
            for topic in content:
                if not isinstance(topic.get('title'),str) or not topic['title'].strip():
                    raise ValueError('Every prayer topic requires its delivered title')
                if not isinstance(topic.get('body',''),str):
                    raise ValueError('Prayer topic body must be text')
        if blocks:
            blocks.append({'kind':'blank','key':f'boundary:{key}'})
        block={'kind':kind,'key':key,'state':item['content']['state'],'content':content}
        if kind=='song' and content is None:
            # Reserved blank slot, never replaced with a guessed song or warning slide.
            block['render']='blank_slot'
        elif kind=='prayer_topics':
            block['screens']=[{'title':t['title'],'body':t.get('body','')} for t in content or []]
        blocks.append(block)
    return PlanResult(blocks,unresolved)


if __name__=='__main__':
    import json
    from pathlib import Path
    root=Path(__file__).parent
    result=build_plan(json.loads((root/'notice-0828.json').read_text()))
    (root/'planned-order.json').write_text(json.dumps({
        'ready_for_production':result.ready,
        'unresolved':result.unresolved,
        'blocks':result.blocks,
        'note':'Planning only; song assets and Bible text have not been rendered.'
    },ensure_ascii=False,indent=2))
