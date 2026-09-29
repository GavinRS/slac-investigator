import {mkdir,rm,copyFile,cp,readdir,readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('.',import.meta.url));
const out=root+'dist';
await rm(out,{recursive:true,force:true});await mkdir(out,{recursive:true});
// Positive asset allowlist. Never copy the repository or runtime artifacts.
await copyFile(root+'index.html',out+'/index.html');
await cp(root+'assets',out+'/assets',{recursive:true});
await cp(root+'data',out+'/data',{recursive:true});
await copyFile(root+'.nojekyll',out+'/.nojekyll');
// Only the reviewed Grid replay is packaged, never arbitrary runtime traces.
const gridFiles=['manifest.json','slac-001.json'];
await mkdir(out+'/grid-replay',{recursive:true});
for(const name of gridFiles)await copyFile(root+'grid-replay/'+name,out+'/grid-replay/'+name);
for(const directory of ['data','grid-replay'])for(const name of await readdir(out+'/'+directory)){
 const body=await readFile(out+'/'+directory+'/'+name,'utf8');
 if(/FLWR_.*API_KEY|sk-proj-|"is_anom"|"anom_type"|"evaluation_labels"/.test(body))throw new Error('Deployment payload contains excluded configuration or labels.');
}
console.log('Built frontend/dist with index.html, assets/, data/, .nojekyll and two explicitly allowed Grid replay JSON files.');
