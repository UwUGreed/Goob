import {describe,it,expect} from 'vitest';
import {initialState,reducer,eligible,stockRecords,reservedCount} from './simulation';
describe('shared operations records',()=>{
 it('reserves one truck part, rejects stock reductions below reservations and consumes on completion',()=>{
 let s=initialState();s=reducer(s,{type:'assign',techId:'maya',jobId:'oak'});expect(reservedCount(s,'P-02',stockRecords(s)[0].part)).toBe(1);
 expect(reducer(s,{type:'stock',item:{...stockRecords(s)[0],quantity:0}})).toBe(s);
 s=reducer(reducer(reducer(reducer(s,{type:'start',techId:'maya'}),{type:'tick',dt:1000}),{type:'work',techId:'maya'}),{type:'complete',techId:'maya'});
 expect(stockRecords(s)[0].quantity).toBe(2);expect(reservedCount(s,'P-02',stockRecords(s)[0].part)).toBe(0);
 });
 it('warehouse stock cannot satisfy a truck requirement and negative stock is rejected',()=>{
 let s=initialState();s=reducer(s,{type:'stock',item:{...stockRecords(s)[0],quantity:0}});expect(eligible(s,'maya','oak')).toBe(false);
 s=reducer(s,{type:'stock',item:{...stockRecords(s)[0],id:'warehouse',truck:'Warehouse',quantity:10}});expect(eligible(s,'maya','oak')).toBe(false);
 expect(reducer(s,{type:'stock',item:{...stockRecords(s)[0],quantity:-1}})).toBe(s);
 });
});
