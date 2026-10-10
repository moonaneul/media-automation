import fs from 'node:fs/promises';
import path from 'node:path';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
const root=path.resolve(import.meta.dirname,'..');
const input=JSON.parse(await fs.readFile(path.join(root,'planned-order.json'),'utf8'));
const screens=input.blocks.find(b=>b.kind==='prayer_topics').screens;
const p=Presentation.create({slideSize:{width:960,height:720}});
for(const [i,screen] of screens.entries()) {
 const s=p.slides.add(); s.background.fill='#FFFFFF';
 const add=(text,top,height,size,bold)=>{
  const box=s.shapes.add({geometry:'textbox',position:{left:60,top,width:840,height},fill:'none',line:{fill:'none',width:0}});
  box.text=text;
  box.text.style={typeface:'Apple SD Gothic Neo',fontSize:size,bold,color:'#000000',alignment:'center',verticalAlignment:'middle'};
 };
 add(screen.title,230,95,38,true);
 add(screen.body,340,145,32,false);
 const png=await p.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(root,'build',`prayer-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
const candidate=path.join(root,'build','prayer-candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidate);
const skill='/Users/LOCAL_USER/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
const {finalizePresentation}=await import(path.join(skill,'container_tools/artifact_tool_utils.mjs'));
await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:path.join(root,'output','friday-prayer-topics.pptx'),pythonExecutable:'/Users/LOCAL_USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','9144000,6858000','--validate-heading-fit'],fontPolicy:{basis:'design',families:['Apple SD Gothic Neo']},verifyArtifactToolImport:true,receiptPath:path.join(root,'build','validation.json')});
