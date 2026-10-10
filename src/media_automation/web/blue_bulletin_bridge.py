"""Minimal, guarded behavior bridge for the unchanged blue HTML / input fields.

The original UI source remains a read-only reference. Only the served JS
receives an import helper. No worship field structure or visual design is
recreated.
"""
from __future__ import annotations


def _replace_once(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise RuntimeError("원래 안내문 입력 코드가 변경되었습니다. 임의 수정 없이 검토해주세요.")
    return source.replace(before, after, 1)


_AUTO_APPLY = r"""
function copySundaySharingToSermon(){
    if(service!=='sunday')return;
    const r=record();
    const candidate=SundayHwpAutofill.planSermonCopy(r.fields);
    if(!candidate.ready)return msg(candidate.message);
    const passage=r.fields['목장 본문'].value;
    const heading=r.fields['목장 제목'].value;
    if(!confirm(
        '이번 주 주일 PPT의 본문과 설교 제목이 목장 나눔과 동일한가요?\n\n'
        +'본문: '+passage+'\n설교 제목: '+heading
        +'\n\n같은 내용일 때만 [확인]을 누르세요.'
    ))return;
    const latest=SundayHwpAutofill.planSermonCopy(record().fields);
    if(!latest.ready)return msg(latest.message);
    for(const [label,value] of Object.entries(latest.updates)){
        r.fields[label]={...value};
    }
    markChanged();
    render();
    msg('확인한 목장 본문과 제목을 이번 주 주일 PPT 입력칸에도 반영했습니다.');
}
function autoApplySundayHwp(){
    if(service!=='sunday'||!pendingDraft)return;
    const draft=pendingDraft;
    const target=day(6);
    const targetLabel=(target.getMonth()+1)+'/'+target.getDate();
    const policy=SundayHwpAutofill.plan(draft.parsed,draft.info?.dateLabel,targetLabel,record().fields);
    if(policy.dateMismatch){
        msg('HWP 날짜가 선택한 주일과 다릅니다. 입력을 자동 변경하지 않았습니다. 먼저 날짜를 확인해주세요.');
        return;
    }
    const r=record();
    const applied=[];
    r.source=draft.raw;
    r.sourceValues??={};
    r.noticeSongList=draft.info?.songList||'';
    for(const [label,value] of Object.entries(policy.updates)){
        if(!fieldNames().includes(label))continue;
        r.fields[label]={...value};
        r.sourceValues[label]={...value};
        applied.push(label);
    }
    r.noticeImportSummary={
        applied,
        review:policy.review,
        preserved:policy.preserved,
        songList:r.noticeSongList,
    };
    markChanged();
    render();
    $('notice-dialog').close();
    msg('주보 HWP에서 '+applied.length+'개 항목을 자동 반영했습니다. 설거지·기도 담당자 등 섬김표는 원본 표 확인 후 적용해주세요.');
}
"""



_PROGRESS_AUDIT = r"""
function updateSundayInputSourceExplanation(){
    const sidebar=$('input-progress-list');
    let note=document.getElementById('sunday-source-explanation');
    if(service!=='sunday'||!record().noticeImportSummary){
        if(note)note.remove();
        return;
    }
    if(!note){
        note=node('p',undefined,'hint');
        note.id='sunday-source-explanation';
        sidebar.before(note);
    }
    const r=record();
    const pptLabels=[
        '시작 찬양 1','시작 찬양 2','시작 찬양 3','별도 찬송',
        '주일 인도자','1부 찬양 인도자','2부 찬양 인도자',
        '봉헌 찬송','특송','성경 본문','설교 제목','결단 찬송'
    ];
    const required=pptLabels.filter(label=>{
        const f=r.fields[label];
        return !(f?.state==='VALUE'&&String(f.value||'').trim())&&f?.state!=='NONE';
    });
    const imported=r.noticeImportSummary||{};
    const review=Array.isArray(imported.review)?imported.review.length:0;
    const songs=imported.songList?
        ' · 주보 찬양 '+imported.songList+' (사용 순서 미지정)':'';
    note.textContent='전달 주보 자동 입력 '+(imported.applied?.length||0)+
        '개 · 별도 주일예배 안내가 필요한 미입력 '+required.length+
        '개 · 섬김표 원본 대조 '+review+'개'+songs+
        '. ○는 인식 실패만을 의미하지 않습니다. HWP에 없는 예배 순서는 임의로 채우지 않습니다.';
}
"""

def patch_original_script(script: str) -> str:
    script = _replace_once(
        script,
        "function parse(){const raw=$('notice-text').value;",
        _AUTO_APPLY + "\nfunction parse(){const raw=$('notice-text').value;",
    )
    script = _replace_once(
        script,
        "pendingDraft={raw,parsed,unknown};",
        "pendingDraft={raw,parsed,unknown,info:fridayParsed};",
    )
    script = _replace_once(
        script,
        "const c=node('input');c.type='checkbox';c.checked=true;",
        "const c=node('input');c.type='checkbox';"
        "c.checked=!(service==='sunday'&&fridayParsed&&SundayHwpAutofill.isTableReview(label))"
        "&&(!old||old.state==='UNSET'||(old.state===value.state&&old.value===value.value));",
    )
    script = _replace_once(
        script,
        "parse();msg('파일을 읽고 항목을 찾았습니다. 아래 해석 결과를 확인한 뒤 [선택 항목 반영]을 눌러야 입력칸에 저장됩니다.');",
        "parse();"
        "if(service==='sunday'&&/\\.hwp$/i.test(f.name)){autoApplySundayHwp();}"
        "else msg('추출된 항목을 확인한 뒤 [선택 항목 반영]을 눌러주세요.');",
    )
    insertion = (
        "if(service==='sunday'&&record().noticeImportSummary){"
        "const s=record().noticeImportSummary;"
        "const note=node('div',undefined,'panel intro');"
        "const inner=node('div',undefined,'panel-body');"
        "inner.append(node('h3','전달 주보 자동 입력 결과'));"
        "inner.append(node('p','반영 '+s.applied.length+'개 · 표 확인 필요 '+s.review.length+"
        "'개 · 기존 입력 보존 '+s.preserved.length+'개','hint'));"
        "if(s.review.length){const btn=node('button','섬김표 후보 확인');"
        "btn.onclick=()=>{$('notice-text').value=record().source;parse();$('notice-dialog').showModal();};"
        "inner.append(btn);}"

        "const sermon=SundayHwpAutofill.planSermonCopy(record().fields);"
        "const sermonText=node('p','주일 PPT 본문·설교 제목: '+sermon.message,'hint');"
        "inner.append(sermonText);"
        "if(sermon.ready){const copy=node('button','목장 본문·제목을 주일 PPT에도 사용');"
        "copy.onclick=copySundaySharingToSermon;inner.append(copy);}"
        "note.append(inner);root.append(note);}"
    )
    script = _replace_once(
        script,
        "function renderInputProgress(){",
        _PROGRESS_AUDIT + "\nfunction renderInputProgress(){",
    )
    script = _replace_once(
        script,
        " $('progress-count').textContent=filled+' / '+total+' 확인';",
        " $('progress-count').textContent=filled+' / '+total+' 입력상태';"
        "updateSundayInputSourceExplanation();",
    )
    script = _replace_once(
        script,
        "const root=$('form-groups');root.replaceChildren();",
        "const root=$('form-groups');root.replaceChildren();" + insertion,
    )
    return script
