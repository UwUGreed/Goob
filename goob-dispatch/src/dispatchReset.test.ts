import {describe,it,expect} from 'vitest';
import {initialState,reducer} from './simulation';
describe('database Dispatch reset',()=>{
 it('pauses every technician and clears ephemeral replay without modifying business records',()=>{
  const base=initialState();const state={...base,databaseBacked:true,speed:10,technicians:{...base.technicians,maya:{...base.technicians.maya,running:true,progress:.4,replay:{progress:.2,running:true}}}};
  const reset=reducer(state,{type:'reset'});
  expect(reset.speed).toBe(1);expect(reset.technicians.maya.running).toBe(false);expect(reset.technicians.maya.replay).toBeUndefined();expect(reset.technicians.maya.progress).toBe(.4);
  expect(reset.jobs).toBe(state.jobs);expect(reset.stock).toBe(state.stock);expect(reset.customers).toBe(state.customers);expect(reset.technicians.maya.jobId).toBe(state.technicians.maya.jobId);
  expect(reducer(reset,{type:'tick',dt:100})).toEqual(reset);
 });
});
