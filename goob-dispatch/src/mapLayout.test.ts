import { describe, expect, it } from 'vitest';
import { layoutLabels, overlaps, type ScreenLabel } from './mapLayout';
const labels:ScreenLabel[]=[
  {id:'maya',anchor:{x:72,y:295},width:172,height:48,priority:20,above:true},
  {id:'oak',anchor:{x:304,y:295},width:157,height:44,priority:20,above:false},
  {id:'chris',anchor:{x:166,y:164},width:111,height:31,priority:10,above:true},
  {id:'jordan',anchor:{x:295,y:166},width:128,height:31,priority:10,above:true},
  {id:'maple',anchor:{x:166,y:100},width:145,height:39,priority:5,above:false},
  {id:'cedar',anchor:{x:295,y:166},width:143,height:39,priority:5,above:false},
  {id:'depot',anchor:{x:72,y:295},width:108,height:27,priority:1,above:false},
];
describe('map label placement',()=>{
  it('keeps every district label on screen without overlapping labels or controls',()=>{
    const controls=[{x:12,y:12,width:162,height:42},{x:10,y:378,width:275,height:38},{x:306,y:305,width:37,height:106},{x:234,y:263,width:108,height:34}];
    const placed=layoutLabels(labels,354,440,controls);expect(placed).toHaveLength(labels.length);
    placed.forEach((label,i)=>{expect(label.x).toBeGreaterThanOrEqual(12);expect(label.y).toBeGreaterThanOrEqual(12);expect(label.x+label.width).toBeLessThanOrEqual(342);expect(label.y+label.height).toBeLessThanOrEqual(428);expect(controls.some(rect=>overlaps(label,rect))).toBe(false);expect(placed.slice(i+1).some(other=>overlaps(label,other))).toBe(false);});
  });
  it('prioritizes selected labels even when space cannot contain all secondary labels',()=>{
    const placed=layoutLabels(labels,240,220,[]);expect(placed.some(label=>label.id==='maya')).toBe(true);expect(placed.some(label=>label.id==='oak')).toBe(true);
  });
});
