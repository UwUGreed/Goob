import {describe,it,expect} from 'vitest';
import {initialState,freshDemoState,reducer} from './simulation';
import {jobs} from './data';
describe('database Dispatch reset',()=>{
 it('pauses every technician and clears ephemeral replay without modifying business records',()=>{
  const base=initialState();const state={...base,databaseBacked:true,speed:10,technicians:{...base.technicians,maya:{...base.technicians.maya,running:true,progress:.4,replay:{progress:.2,running:true}}}};
  const reset=reducer(state,{type:'reset'});
  expect(reset.speed).toBe(1);expect(reset.technicians.maya.running).toBe(false);expect(reset.technicians.maya.replay).toBeUndefined();expect(reset.technicians.maya.progress).toBe(.4);
  expect(reset.jobs).toBe(state.jobs);expect(reset.stock).toBe(state.stock);expect(reset.customers).toBe(state.customers);expect(reset.technicians.maya.jobId).toBe(state.technicians.maya.jobId);
  expect(reducer(reset,{type:'tick',dt:100})).toEqual(reset);
 });
});


describe('completed visit replay',()=>{
 it('rebuilds travel after refresh and permits repeated playback without business changes',()=>{
  const base=initialState();const state={...base,databaseBacked:true,jobs:{...base.jobs,cedar:'Completed' as const},technicians:{...base.technicians,jordan:{...base.technicians.jordan,status:'Completed' as const,route:[],duration:0}}};
  const replay=reducer(state,{type:'replay',techId:'jordan'});
  expect(replay.technicians.jordan.route.length).toBeGreaterThan(1);
  expect(replay.technicians.jordan.replay?.running).toBe(true);
  const paused=reducer(replay,{type:'pause',techId:'jordan'});
  expect(paused.technicians.jordan.replay?.running).toBe(false);
  const resumed=reducer(paused,{type:'start',techId:'jordan'});
  expect(resumed.technicians.jordan.replay?.running).toBe(true);
  const ended=reducer(resumed,{type:'tick',dt:1000});
  expect(ended.technicians.jordan.replay).toEqual({progress:1,running:false});
  expect(ended.technicians.jordan.status).toBe('Completed');
  expect(ended.jobs).toEqual(state.jobs);expect(ended.stock).toBe(state.stock);
  expect(reducer(ended,{type:'replay',techId:'jordan'}).technicians.jordan.replay).toEqual({progress:0,running:true});
 });
 it('leaves a completed visit with unknown location untouched',()=>{
  const base=initialState();const state={...base,databaseBacked:true,records:[{...jobs[0],id:'unknown',node:'unknown'}],technicians:{...base.technicians,jordan:{...base.technicians.jordan,status:'Completed' as const,jobId:'unknown'}}};
  expect(reducer(state,{type:'replay',techId:'jordan'})).toBe(state);
 });
});


describe('fresh demo sandbox',()=>{
 it('starts and resets with all visits unassigned and all trucks available',()=>{
  const fresh=freshDemoState();expect(Object.values(fresh.jobs).every(s=>s==='Unassigned')).toBe(true);
  expect(Object.values(fresh.technicians).every(t=>t.status==='Available')).toBe(true);
  expect(fresh.databaseBacked).toBe(false);expect(fresh.demoSandbox).toBe(true);
  expect(reducer({...fresh,jobs:{...fresh.jobs,oak:'Completed'}},{type:'reset'})).toEqual(fresh);
 });
});
