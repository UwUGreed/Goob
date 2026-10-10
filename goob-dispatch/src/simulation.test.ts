import { describe, expect, it } from 'vitest';
import { initialState, reducer, eligible } from './simulation';
import { findRoute, nodes, edges, pointOnRoute, distance } from './routing';
import { jobs, depot } from './data';
describe('dispatch approval and eligibility',()=>{
  it('only assigns an available technician with matching skills and parts',()=>{
    const initial=initialState();expect(eligible(initial,'maya','oak')).toBe(true);expect(eligible(initial,'chris','oak')).toBe(false);expect(eligible(initial,'jordan','oak')).toBe(false);
    expect(reducer(initial,{type:'assign',techId:'chris',jobId:'oak'})).toBe(initial);
    const assigned=reducer(initial,{type:'assign',techId:'maya',jobId:'oak'});
    expect(assigned.technicians.maya.status).toBe('Assigned');expect(assigned.technicians.maya.running).toBe(false);expect(assigned.jobs.oak).toBe('Assigned');
    expect(reducer(assigned,{type:'assign',techId:'maya',jobId:'oak'})).toBe(assigned);
    expect(reducer(assigned,{type:'assign',techId:'maya',jobId:'willow'})).toBe(assigned);
  });
  it('rejects working or completing before arrival',()=>{
    const s=reducer(initialState(),{type:'assign',techId:'maya',jobId:'oak'});
    expect(reducer(s,{type:'work',techId:'maya'})).toBe(s);expect(reducer(s,{type:'complete',techId:'maya'})).toBe(s);
  });
});
describe('journey lifecycle',()=>{
  function arrived(){let s=initialState();s=reducer(s,{type:'assign',techId:'maya',jobId:'oak'});s=reducer(s,{type:'start',techId:'maya'});return reducer(s,{type:'tick',dt:1000});}
  function completed(){return reducer(reducer(arrived(),{type:'work',techId:'maya'}),{type:'complete',techId:'maya'});}
  it('requires start, preserves progress on pause and view changes, and resumes at the same location',()=>{
    let s=reducer(initialState(),{type:'assign',techId:'maya',jobId:'oak'});
    s=reducer(s,{type:'tick',dt:10});expect(s.technicians.maya.progress).toBe(0);
    s=reducer(s,{type:'start',techId:'maya'});s=reducer(s,{type:'tick',dt:5});const p=s.technicians.maya.progress;expect(p).toBeGreaterThan(0);
    s=reducer(s,{type:'pause',techId:'maya'});s=reducer(s,{type:'tick',dt:10});expect(s.technicians.maya.progress).toBe(p);
    // View mode is UI state, entirely absent from simulation actions.
    expect(Object.keys(s)).not.toContain('mode');
    s=reducer(s,{type:'start',techId:'maya'});s=reducer(s,{type:'tick',dt:1});expect(s.technicians.maya.progress).toBeGreaterThan(p);
  });
  it('stops on arrival, completes on request, returns to depot and becomes available',()=>{
    let s=arrived();expect(s.technicians.maya.status).toBe('Arrived');expect(s.technicians.maya.running).toBe(false);expect(s.technicians.maya.node).toBe(jobs[0].node);
    s=reducer(s,{type:'work',techId:'maya'});expect(s.jobs.oak).toBe('Working');s=reducer(s,{type:'complete',techId:'maya'});expect(s.jobs.oak).toBe('Completed');
    s=reducer(s,{type:'return',techId:'maya'});expect(s.technicians.maya.status).toBe('Returning');expect(s.technicians.maya.route[0]).toEqual(nodes[jobs[0].node]);
    expect(reducer(s,{type:'assign',techId:'maya',jobId:'willow'})).toBe(s);
    s=reducer(s,{type:'tick',dt:1000});expect(s.technicians.maya.status).toBe('Available');expect(s.technicians.maya.node).toBe(depot);expect(s.jobs.oak).toBe('Completed');
  });
  it('allows a subsequent plumbing visit from the completed visit location',()=>{
    const s=reducer(completed(),{type:'assign',techId:'maya',jobId:'willow'});expect(s.jobs.willow).toBe('Assigned');expect(s.technicians.maya.route[0]).toEqual(nodes[jobs[0].node]);
    expect(eligible(initialState(),'maya','willow')).toBe(false);
  });
  it('uses the selected speed and resets all demo state',()=>{
    const base=reducer(reducer(initialState(),{type:'assign',techId:'maya',jobId:'oak'}),{type:'start',techId:'maya'});
    const one=reducer(base,{type:'tick',dt:1}),five=reducer(reducer(base,{type:'speed',speed:5}),{type:'tick',dt:1});expect(five.technicians.maya.progress).toBeCloseTo(one.technicians.maya.progress*5);expect(reducer(five,{type:'reset'})).toEqual(initialState());
  });
  it('supports independent technicians without overwriting assignments',()=>{
    let s=reducer(initialState(),{type:'assign',techId:'maya',jobId:'oak'});s=reducer(s,{type:'assign',techId:'chris',jobId:'maple'});s=reducer(s,{type:'start',techId:'maya'});s=reducer(s,{type:'start',techId:'chris'});s=reducer(s,{type:'tick',dt:1});expect(s.technicians.maya.progress).toBeGreaterThan(0);expect(s.technicians.chris.progress).toBeGreaterThan(0);expect(s.jobs.cedar).toBe('Working');
  });
});
describe('fictional street network',()=>{
  it('connects all demo locations using street edges',()=>{
    for(const from of Object.keys(nodes))for(const job of jobs){const route=findRoute(from,job.node);expect(route[0]).toEqual(nodes[from]);expect(route.at(-1)).toEqual(nodes[job.node]);for(let i=1;i<route.length;i++){expect(edges.some(([a,b])=>(nodes[a]===route[i-1]&&nodes[b]===route[i])||(nodes[b]===route[i-1]&&nodes[a]===route[i]))).toBe(true);}}
  });
  it('interpolates on streets and clamps at endpoints',()=>{
    const route=findRoute(depot,jobs[0].node);for(let f=0;f<=1;f+=.01){const p=pointOnRoute(route,f);expect(route.slice(1).some((b,i)=>Math.abs(distance(route[i],p)+distance(p,b)-distance(route[i],b))<.001)).toBe(true);}expect(pointOnRoute(route,2)).toMatchObject(route.at(-1)!);
  });
});
