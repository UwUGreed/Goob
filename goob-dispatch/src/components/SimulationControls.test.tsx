import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {SimulationControls} from './SimulationControls';
import {initialState} from '../simulation';
describe('completed travel controls',()=>{
 it('offers an enabled replay after a completed visit refresh',()=>{
  const base=initialState();const state={...base,technicians:{...base.technicians,jordan:{...base.technicians.jordan,status:'Completed' as const}}};
  const html=renderToStaticMarkup(<SimulationControls state={state} techId="jordan" dispatch={()=>{}} reduced={false} onReset={()=>{}}/>);
  expect(html).toContain('Replay</button>');
  expect(html).not.toMatch(/class="play-button[^"]*" disabled/);
  expect(html).toContain('Saved completion and inventory stay unchanged');
 });
});
