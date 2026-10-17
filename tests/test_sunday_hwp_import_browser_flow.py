"""Run the actual Sunday browser import function with a DOM-lite test harness.

No real church names are committed. The flattened source shape matches a full
Sunday serving table and the previous local fields contain stale parser errors.
"""
import json
import subprocess
from pathlib import Path


def test_importing_corrected_hwp_replaces_stale_none_and_wrong_offering_value():
    node=r"""
    const fs=require('fs'),p=require(process.argv[1]);
    const html=fs.readFileSync(process.argv[2],'utf8');
    const src=html.slice(html.indexOf('function parse(){'),
                         html.indexOf("document.querySelectorAll('[data-page]')"));
    const raw=[
      '주보 교회','10/18','*예배 / 섬김 :',
      '구 분','기 도','봉 헌 기 도','설 거 지','수요예배 기도',
      '이 번 주','1 부','인도자','첫봉헌','설거지첫째','수요첫째',
      '2 부','정확한기도자','정확한봉헌자',
      '다 음 주','1 부','인도자','다음봉헌','다음설거지','다음수요',
      '2 부','다음기도','다음봉헌2',
      '*1면 –','<목장 말씀 나누기>','<시 1:1 / 제목>','1. 질문'
    ].join('\n');
    const stored={
      fields:{
        '2부 기도 담당자':{state:'NONE',value:''},
        '2부 봉헌기도 담당자':{state:'VALUE',value:'설거지'},
        '이번 주 설거지':{state:'VALUE',value:'사람이 수정한 설거지'},
      },
      sourceValues:{
        '2부 기도 담당자':{state:'NONE',value:''},
        '2부 봉헌기도 담당자':{state:'VALUE',value:'설거지'},
        '이번 주 설거지':{state:'VALUE',value:'처음 자동값'},
      },
      manualOverrides:{'이번 주 설거지':true},
      outputs:{ppt:{generated:false}}
    };
    let preview=[],applied=false,msgText='',closed=false,rendered=false;
    const panel={
      hidden:true,children:[],replaceChildren(){this.children=[]},
      append(...items){this.children.push(...items)},
      querySelectorAll(query){
        if(query!=="input[data-label]:checked")throw Error(query);
        return preview.filter(x=>x.checked);
      },
      querySelector(query){
        const label=query.match(/data-label="([^"]+)"/)?.[1];
        return preview.find(x=>x.dataset.label===label&&x.checked)||null;
      }
    };
    const input={value:raw};
    const $=id=>id==='parse-review'?panel:id==='notice-text'?input:
      id==='notice-dialog'?{close(){closed=true}}:null;
    const node=(tag,txt,cls)=>{
      const obj={tag,txt,cls,dataset:{},items:[],append(...children){
        this.items.push(...children);for(const child of children)
          if(child.tag==='input'&&child.dataset.label)preview.push(child);
      }};
      if(tag==='button'&&txt==='선택 항목 반영')globalThis.apply=obj;
      return obj;
    };
    const service='sunday',aliases={},noticeDocument={text:raw,tables:[]};
    const record=()=>stored,fieldNames=()=>[
      '2부 기도 담당자','2부 봉헌기도 담당자','이번 주 설거지',
      '이번 주 1부 봉헌기도','다음 주 2부 기도','다음 주 2부 봉헌기도'
    ];
    const key=()=> 'sunday:2026-10-18',day=()=>new Date('2026-10-18T12:00:00');
    const iso=()=> '2026-10-18',markChanged=()=>applied=true;
    const render=()=>rendered=true,msg=x=>msgText=x;
    const shared=false,fridayMode=()=> 'zoom',syncState=()=>({loaded:true});
    const NoticeParser=p, pendingDraft=null;
    eval(src);
    parse();
    const selected=preview.filter(x=>x.checked).map(x=>x.dataset.label);
    if(!selected.includes('2부 기도 담당자')||!selected.includes('2부 봉헌기도 담당자'))
      throw Error('Stale parser error is still unchecked');
    if(selected.includes('이번 주 설거지'))throw Error('User edit would be overwritten');
    if(!globalThis.apply?.onclick)throw Error('Import action missing');
    globalThis.apply.onclick();
    console.log(JSON.stringify({selected,prayer:stored.fields['2부 기도 담당자'],
      offering:stored.fields['2부 봉헌기도 담당자'],
      dishwashing:stored.fields['이번 주 설거지'],closed,rendered,applied,msgText}));
    """
    root=Path("src/media_automation/web/original/ui")
    result=json.loads(subprocess.check_output(
        ["node","-e",node,str((root/"notice-parser.js").resolve()),
         str((root/"index.html").resolve())],text=True,timeout=7))
    assert result["prayer"]=={"state":"VALUE","value":"정확한기도자"}
    assert result["offering"]=={"state":"VALUE","value":"정확한봉헌자"}
    assert result["dishwashing"]=={"state":"VALUE","value":"사람이 수정한 설거지"}
    assert result["closed"] and result["applied"] and result["rendered"]
