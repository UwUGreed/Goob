import { build } from 'esbuild';
import { readFile, readdir, mkdir, cp } from 'node:fs/promises';
import path from 'node:path';
const root=process.cwd(),client=path.join(root,'dist'),assets={};
const types={'.html':'text/html;charset=utf-8','.js':'text/javascript;charset=utf-8','.css':'text/css;charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon'};
async function walk(dir){for(const entry of await readdir(dir,{withFileTypes:true})){if(entry.name==='server'||entry.name==='.openai')continue;const file=path.join(dir,entry.name);if(entry.isDirectory())await walk(file);else assets['/'+path.relative(client,file).replaceAll('\\','/')]={body:(await readFile(file)).toString('base64'),type:types[path.extname(file)]??'application/octet-stream'};}}
await walk(client);await mkdir(path.join(client,'server'),{recursive:true});
await build({entryPoints:['server/index.ts'],outfile:'dist/server/index.js',bundle:true,format:'esm',platform:'browser',target:'es2022',minify:true,plugins:[{name:'client-assets',setup(builder){builder.onResolve({filter:/^virtual:client-assets$/},()=>({path:'client-assets',namespace:'goob-assets'}));builder.onLoad({filter:/.*/,namespace:'goob-assets'},()=>({contents:`export default ${JSON.stringify(assets)}`,loader:'js'}));}}]});
await mkdir(path.join(client,'.openai'),{recursive:true});await cp('.openai/hosting.json','dist/.openai/hosting.json');await cp('drizzle','dist/.openai/drizzle',{recursive:true});
console.log(`Built authenticated Worker with ${Object.keys(assets).length} embedded client assets.`);
