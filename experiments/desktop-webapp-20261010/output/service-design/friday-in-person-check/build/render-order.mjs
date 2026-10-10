import fs from 'node:fs/promises';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';
const p=await PresentationFile.importPptx(await FileBlob.load('../output/friday-order-preview.pptx'));
const png=await p.export({format:'webp',montage:true});
await fs.writeFile('order-montage.webp',new Uint8Array(await png.arrayBuffer()));
