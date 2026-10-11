import assets from 'virtual:client-assets';
type Env={GOOB_BACKEND_URL?:string};
export default {async fetch(request:Request,env:Env){
  const source=new URL(request.url),path=source.pathname;
  if(path.startsWith('/api/')){
    if(!env.GOOB_BACKEND_URL)return Response.json({error:'Configure the Tiger Cloud application backend URL.'},{status:503});
    const target=new URL(path+source.search,env.GOOB_BACKEND_URL);
    if(target.protocol!=='https:')return Response.json({error:'The application backend must use HTTPS.'},{status:503});
    try{return await fetch(new Request(target,request));}catch{return Response.json({error:'The database-backed application server is unavailable.'},{status:503});}
  }
  if(path==='/terms'||path==='/privacy')return new Response(legal(path),{headers:{'Content-Type':'text/html;charset=utf-8'}});
  const asset=assets[path==='/'?'/index.html':path]??(!path.includes('.')?assets['/index.html']:undefined);
  if(!asset)return new Response('Not found',{status:404});
  const bytes=Uint8Array.from(atob(asset.body),c=>c.charCodeAt(0));return new Response(bytes,{headers:{'Content-Type':asset.type,'Cache-Control':path.startsWith('/assets/')?'public, max-age=31536000, immutable':'no-cache','X-Content-Type-Options':'nosniff'}});
}};
function legal(path:string){return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Goob demo ${path.slice(1)}</title><style>body{max-width:700px;margin:60px auto;padding:24px;background:#faf8f2;color:#342434;font:17px/1.7 system-ui}a{color:#634766}h1{font-family:Georgia}</style><a href="/">Return to dispatch</a><h1>${path==='/terms'?'Demo terms of use':'Demo privacy notice'}</h1><p>This is a fictional dispatch demonstration. No technicians, customers, assignments, or inventory in this demo represent real operations. Maps display public geography; movement is simulated.</p>${path==='/terms'?'<p>Google Maps features are subject to <a href="https://maps.google.com/help/terms_maps/">Google Maps terms</a> and the <a href="https://policies.google.com/privacy">Google privacy policy</a>. Do not rely on this demonstration for navigation or emergency dispatch.</p>':'<p>View preferences remain on your device. Dispatch sessions and request counters are held on the server. Google receives route locations when real-map routing is configured. Google route results remain in active browser memory and are discarded on reload. Microphone audio is sent to ElevenLabs only after you click Start microphone. Transcript text is editable and is not persisted by Goob. Stopping or canceling releases microphone access.</p><p>See the <a href="https://policies.google.com/privacy">Google privacy policy</a> and <a href="https://elevenlabs.io/privacy-policy">ElevenLabs privacy policy</a> for provider handling. The deployment owner must provide their contact, retention policy, and publicly accessible production policies before offering this integration publicly.</p>'}</html>`;}
