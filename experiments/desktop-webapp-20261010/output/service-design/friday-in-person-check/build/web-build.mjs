import fs from 'node:fs/promises';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
const args=JSON.parse(await fs.readFile(process.argv[2],'utf8'));
const width=args.zoom?1280:960,height=720;
const p=Presentation.create({slideSize:{width,height}});
const mapping=[],unresolved=[];
for(const block of args.order){
 if(block.kind==='input'&&block.state!=='VALUE'){if(block.state==='UNSET')unresolved.push(block.key);continue;}
 const passage=args.bible?.[block.key];
 if(block.kind==='input'&&passage?.units?.length){
  const start=p.slides.items.length+1;
  for(const unit of passage.units){
   const slide=p.slides.add();slide.background.fill='#FFFFFF';
   const ref=slide.shapes.add({geometry:'textbox',position:{left:76,top:52,width:width-152,height:65},fill:'none',line:{fill:'none',width:0}});
   ref.text=unit.passage_reference||block.content||unit.reference;ref.text.style={typeface:'Apple SD Gothic Neo',fontSize:36,color:'#000000',alignment:'left'};
   const body=slide.shapes.add({geometry:'textbox',position:{left:76,top:160,width:width-152,height:450},fill:'none',line:{fill:'none',width:0}});
   body.text='['+unit.start_verse+(unit.combined?'~'+unit.end_verse:'')+'] '+unit.text.replaceAll('세례','침례');
   body.text.style={typeface:'Apple SD Gothic Neo',fontSize:unit.text.length>=150?37.33:unit.text.length>=100?40:42.67,color:'#000000',alignment:'left',verticalAlignment:'middle',lineSpacing:1.45};
  }
  mapping.push({key:block.key,kind:block.kind,start,end:p.slides.items.length,status:'bible_inserted',translation:'개역개정'});
  continue;
 }
 const s=p.slides.add();s.background.fill='#FFFFFF';
 s.shapes.add({geometry:'rect',position:{left:0,top:0,width,height},fill:'#FFFFFF',line:{fill:'none',width:0}});
 let status='rendered';
 if(block.kind==='song'){status='missing_song_asset';unresolved.push(block.key+':score_asset');}
 else if(block.kind==='input'&&/성경 본문|추가 말씀/.test(block.key)){status='missing_verified_bible_text';unresolved.push(block.key+':bible_text');}
 else if(block.kind==='input'){
  const box=s.shapes.add({geometry:'textbox',position:{left:60,top:block.subtitle?180:160,width:width-120,height:block.subtitle?250:400},fill:'none',line:{fill:'none',width:0}});
  box.text=block.content;
  if(block.subtitle){const subtitle=s.shapes.add({geometry:'textbox',position:{left:60,top:455,width:width-120,height:80},fill:'none',line:{fill:'none',width:0}});subtitle.text=block.subtitle;subtitle.text.style={typeface:'Apple SD Gothic Neo',fontSize:34.67,color:'#000000',alignment:'center',verticalAlignment:'middle'};}
  box.text.style={typeface:'Apple SD Gothic Neo',fontSize:42.67,color:'#000000',alignment:'center',verticalAlignment:'middle',lineSpacing:1.45};
 }
 mapping.push({key:block.key,kind:block.kind,start:p.slides.items.length,end:p.slides.items.length,status});
}
if(!p.slides.items.length)throw new Error('제작할 입력이 없습니다');
await(await PresentationFile.exportPptx(p)).save(args.output);
if(args.previewDir){await fs.mkdir(args.previewDir,{recursive:true});for(const [index,slide] of p.slides.items.entries()){const png=await p.export({slide,format:'png',scale:1});await fs.writeFile(args.previewDir+'/'+(index+1)+'.png',new Uint8Array(await png.arrayBuffer()));}}
await fs.writeFile(args.report,JSON.stringify({slide_count:p.slides.items.length,mapping,unresolved,complete:false,visual_review_pending:true}));
