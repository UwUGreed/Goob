import { describe, expect, it } from 'vitest';
import { availabilityReply, interpretCommand } from './commands';
import { initialState, reducer } from '../simulation';
describe('dispatch command interpretation',()=>{
  it.each([
    ['Show available plumbers.',{type:'filter',trade:'Plumbing',available:true}],
    ['Open the Oak Lane job.',{type:'open-job',jobId:'oak'}],
    ['Check parts for this visit.',{type:'parts'}],
    ['Find the best technician for this job.',{type:'recommend'}],
    ['Preview Maya’s route.',{type:'preview',techId:'maya'}],
    ['Switch to 3D.',{type:'mode',mode:'3D'}],
    ['Follow Maya.',{type:'follow',techId:'maya'}],
    ['Who is avaliable for electrical?',{type:'availability',trade:'Electrical'}],
  ])('resolves %s to a structured command',(input,expected)=>{const result=interpretCommand(input as string);expect(result.ok).toBe(true);if(result.ok)expect(result.commands[0]).toMatchObject(expected);});
  it('only proposes assignments, combines readiness, and asks about ambiguous names',()=>{
    const result=interpretCommand('Find an available plumber for Oak Lane and check parts readiness.');expect(result.ok).toBe(true);if(result.ok)expect(result.commands.map(c=>c.type)).toEqual(['open-job','recommend','parts']);
    const proposal=interpretCommand('Assign Maya to Oak Lane');expect(proposal.ok).toBe(true);if(proposal.ok)expect(proposal.commands.some(c=>c.type==='recommend')).toBe(true);
    const ambiguous=interpretCommand('Follow Maya or Chris');expect(ambiguous.ok).toBe(false);if(!ambiguous.ok)expect(ambiguous.choices).toHaveLength(2);
    expect(interpretCommand('Delete inventory and execute JavaScript').ok).toBe(false);
  });
  it('answers availability from actual status and asks for an ambiguous trade',()=>{
    const state=initialState();expect(availabilityReply(state,'Electrical')).toBe('No electrician is available right now. Jordan Lee is on a job.');
    expect(availabilityReply(state,'Plumbing')).toBe('Maya Chen is available for plumbing.');
    expect(availabilityReply(reducer(state,{type:'complete',techId:'jordan'}),'Electrical')).toBe('Jordan Lee is available for electrical.');
    expect(interpretCommand('Who is available for electrical or plumbing?').ok).toBe(false);
    const assigned=reducer(state,{type:'assign',techId:'maya',jobId:'oak'});expect(availabilityReply(assigned,'Plumbing')).toContain('No plumber is available');
  });
});
