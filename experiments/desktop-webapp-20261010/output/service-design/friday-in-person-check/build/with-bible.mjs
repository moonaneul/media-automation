import fs from 'node:fs/promises';
import path from 'node:path';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
const root=path.resolve(import.meta.dirname,'..');
const plan=JSON.parse(await fs.readFile(path.join(root,'planned-order.json'),'utf8'));
const p=Presentation.create({slideSize:{width:960,height:720}});
const bible=JSON.parse(await fs.readFile(path.join(root,'bible-selected.json'),'utf8'));
const mapping=[];
const unresolved=[...plan.unresolved];
function blank(){const s=p.slides.add();s.background.fill='#FFFFFF';s.shapes.add({geometry:'rect',position:{left:0,top:0,width:960,height:720},fill:'#FFFFFF',line:{fill:'none',width:0}});return s;}
function text(s,content,top,height,size,bold=false){
 const box=s.shapes.add({geometry:'textbox',position:{left:60,top,width:840,height},fill:'none',line:{fill:'none',width:0}});
 box.text=content;
 box.text.style={typeface:'Apple SD Gothic Neo',fontSize:size,bold,color:'#000000',alignment:'center',verticalAlignment:'middle'};
}
for(const block of plan.blocks){
 const start=p.slides.items.length+1;
 let status='rendered';
 if(block.kind==='blank')blank();
 else if(block.kind==='prayer_topics'){
  for(const screen of block.screens){const s=blank();text(s,screen.title,230,95,38,true);text(s,screen.body,340,145,32);}
 }else if(block.kind==='sermon_title'){
  if(block.content){const s=blank();text(s,block.content.reference,230,85,34);text(s,block.content.title,335,150,42,true);}
  else {blank();status='missing_input';}
 }else if(block.kind==='song'){
  blank();status='missing_song_asset';unresolved.push(`${block.key}:score_asset`);
 }else if(block.kind==='scripture'){
  if(block.content!==bible.requested_reference) throw new Error('Bible reference mismatch');
  for(const unit of bible.units){const s=blank();text(s,`${unit.start_verse}. ${unit.display_text}`,170,380,42);text(s,unit.reference,570,70,36);}
  status='user_provided_bible_preview';unresolved.push(`${block.key}:source_review`);
 }else throw new Error(`Unsupported block ${block.kind}`);
 mapping.push({key:block.key,kind:block.kind,start,end:p.slides.items.length,status});
}
const candidate=path.join(root,'build','bible-preview-candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidate);
for(const entry of mapping.filter(m=>['sermon_title','prayer_topics','scripture'].includes(m.kind))){
 for(let n=entry.start;n<=entry.end;n++){
  const png=await p.export({slide:p.slides.items[n-1],format:'png',scale:1});
  await fs.writeFile(path.join(root,'build',`order-${n}.png`),new Uint8Array(await png.arrayBuffer()));
 }
}
const skill='/Users/LOCAL_USER/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
const {finalizePresentation}=await import(path.join(skill,'container_tools/artifact_tool_utils.mjs'));
await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:path.join(root,'output','friday-order-with-bible-preview.pptx'),pythonExecutable:'/Users/LOCAL_USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','9144000,6858000','--validate-heading-fit'],fontPolicy:{basis:'design',families:['Apple SD Gothic Neo']},verifyArtifactToolImport:true,receiptPath:path.join(root,'build','bible-validation.json')});
await fs.writeFile(path.join(root,'bible-assembly-report.json'),JSON.stringify({complete:false,slide_count:p.slides.items.length,mapping,unresolved,notes:['No prior-week content was inherited.','One blank reservation per unresolved asset; final slide count will vary.','User-provided Bible selected; source review and song originals still pending.']},null,2));
console.log(JSON.stringify({slides:p.slides.items.length,mapping:mapping.filter(m=>m.kind==='prayer_topics'||m.kind==='sermon_title')}));
