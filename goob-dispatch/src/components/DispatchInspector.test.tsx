import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {DispatchInspector} from './DispatchInspector';
import {initialState} from '../simulation';
import {jobs} from '../data';
describe('Dispatch incomplete jobs',()=>{
 it('keeps a job without technicians, parts or coordinates readable',()=>{
  const job={...jobs[0],id:'canonical-record-id',node:'unknown',requirements:[],part:'No parts required'};
  const state={...initialState(),databaseBacked:true,records:[job],roster:[],technicians:{},jobs:{[job.id]:'Unassigned' as const}};
  const html=renderToStaticMarkup(<DispatchInspector selection={{type:'job',id:job.id}} state={state} slot={null} dispatch={async()=>false} pending={false} realMap onNotice={()=>{}} onSelect={()=>{}}/>);
  expect(html).toContain(job.title);
  expect(html).toContain('No matching technician');
  expect(html).toContain('No parts required');
 });
 it('shows incomplete map and schedule states without allowing an unknown location assignment',()=>{
  const job={...jobs[0],node:'unknown'};const state={...initialState(),records:[job]};
  const html=renderToStaticMarkup(<DispatchInspector selection={{type:'job',id:job.id}} state={state} slot={null} dispatch={async()=>false} pending={false} realMap onNotice={()=>{}} onSelect={()=>{}}/>);
  expect(html).toContain('Verified map coordinates are not recorded');
  expect(html).toContain('No confirmed schedule');
  expect(html).toContain('disabled');
 });
});
