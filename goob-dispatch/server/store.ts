export type StoredSession={revision:number;state:string};
export interface DispatchStore{get(id:string):Promise<StoredSession|null>;create(id:string,state:string):Promise<void>;put(id:string,revision:number,state:string):Promise<boolean>;limit(id:string,window:number,max:number):Promise<boolean>}
interface Statement{bind(...values:unknown[]):Statement;first<T>():Promise<T|null>;run():Promise<{meta:{changes:number}}>}
export interface Database{prepare(sql:string):Statement}
export class D1Store implements DispatchStore{
  constructor(private db:Database){}
  get(id:string){return this.db.prepare('SELECT revision, state FROM dispatch_sessions WHERE id = ?').bind(id).first<StoredSession>();}
  async create(id:string,state:string){await this.db.prepare('INSERT INTO dispatch_sessions (id, state, updated_at) VALUES (?, ?, ?) ON CONFLICT(id) DO NOTHING').bind(id,state,Date.now()).run();}
  async put(id:string,revision:number,state:string){const result=await this.db.prepare('UPDATE dispatch_sessions SET state = ?, revision = revision + 1, updated_at = ? WHERE id = ? AND revision = ?').bind(state,Date.now(),id,revision).run();return result.meta.changes===1;}
  async limit(id:string,window:number,max:number){const result=await this.db.prepare('INSERT INTO dispatch_rate_limits (id, window, count) VALUES (?, ?, 1) ON CONFLICT(id) DO UPDATE SET count = CASE WHEN window = excluded.window THEN count + 1 ELSE 1 END, window = excluded.window RETURNING count').bind(id,window).first<{count:number}>();return !!result&&result.count<=max;}
}
// Local Vite-only store. Hosted requests require the shared D1 binding.
export class MemoryStore implements DispatchStore{
  private sessions=new Map<string,StoredSession>();private limits=new Map<string,{window:number;count:number}>();
  async get(id:string){return this.sessions.get(id)??null;}
  async create(id:string,state:string){if(!this.sessions.has(id))this.sessions.set(id,{revision:0,state});}
  async put(id:string,revision:number,state:string){if(this.sessions.get(id)?.revision!==revision)return false;this.sessions.set(id,{revision:revision+1,state});return true;}
  async limit(id:string,window:number,max:number){const current=this.limits.get(id),next={window,count:current?.window===window?current.count+1:1};this.limits.set(id,next);return next.count<=max;}
}
