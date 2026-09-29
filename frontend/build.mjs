import {mkdir,rm,copyFile,cp,readdir,readFile,access} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('.',import.meta.url));
const out=root+'dist';
await rm(out,{recursive:true,force:true});await mkdir(out,{recursive:true});
// Positive asset allowlist. Never copy the repository or runtime artifacts.
await copyFile(root+'index.html',out+'/index.html');
await cp(root+'assets',out+'/assets',{recursive:true});
await cp(root+'data',out+'/data',{recursive:true});
await copyFile(root+'.nojekyll',out+'/.nojekyll');
// The optional presentation is compiled separately; preserve the original operator console.
try { await access(root+'story/index.html'); await cp(root+'story',out+'/story',{recursive:true}); } catch (error) { if(error.code!=='ENOENT') throw error; }
for(const name of await readdir(out+'/data')){
 const body=await readFile(out+'/data/'+name,'utf8');
 if(/FLWR_.*API_KEY|sk-proj-|"is_anom"|"anom_type"|"evaluation_labels"/.test(body))throw new Error('Deployment payload contains excluded configuration or labels.');
}
console.log('Built frontend/dist with index.html, assets/, data/, optional story/ and .nojekyll.');
