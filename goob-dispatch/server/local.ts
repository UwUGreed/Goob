import type { Plugin } from 'vite';
import { handleApi, type Env } from './api';
import { MemoryStore } from './store';
export function dispatchApi(env:Env):Plugin{
  const store=new MemoryStore();return{name:'goob-local-api',configureServer(server){server.middlewares.use(async(req,res,next)=>{
    if(!['/api/config','/api/dispatch','/api/routes','/api/scribe-token'].includes(req.url?.split('?')[0]??''))return next();
    const authority=`http://${req.headers.host}`,url=new URL(req.url!,authority);
    const localHosts=['127.0.0.1','localhost','[::1]'],remote=['127.0.0.1','::1','::ffff:127.0.0.1'];
    if(!localHosts.includes(url.hostname)||!remote.includes(req.socket.remoteAddress??'')){res.statusCode=403;res.end('Local preview only');return;}
    const chunks:Buffer[]=[];for await(const chunk of req){chunks.push(Buffer.from(chunk));if(chunks.reduce((n,c)=>n+c.length,0)>4096){res.statusCode=413;res.end('Request too large');return;}}
    const headers=new Headers();for(const [key,value]of Object.entries(req.headers))if(value)headers.set(key,Array.isArray(value)?value.join(','):value);
    // This adapter exists only in the loopback development server; production
    // authentication is supplied by Sites and never bypassed by application code.
    headers.set('oai-authenticated-user-id','local-preview-dispatcher');
    const request=new Request(url,{method:req.method,headers,body:req.method==='GET'||req.method==='HEAD'?undefined:Buffer.concat(chunks)});
    try{const response=await handleApi(request,env,store);res.statusCode=response.status;response.headers.forEach((value,key)=>res.setHeader(key,value));res.end(Buffer.from(await response.arrayBuffer()));}catch{res.statusCode=503;res.end('Dispatch server unavailable');}
  });}};
}

