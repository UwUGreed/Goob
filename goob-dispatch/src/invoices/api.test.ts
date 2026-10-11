import {describe,it,expect} from 'vitest';
import {lineCents} from './api';
describe('invoice money uses exact decimal arithmetic',()=>{
 it('rounds fractional quantities once, to cents',()=>{expect(lineCents('0.125','0.05')).toBe(1);expect(lineCents('3','0.10')).toBe(30);expect(lineCents('1.005','1')).toBe(101);});
 it('preserves unresolved and invalid prices',()=>{expect(lineCents('1',null)).toBeNull();expect(lineCents('1','1.005')).toBeNull();expect(lineCents('','150')).toBeNull();});
 it('subtracts credits and rejects negative ordinary charges',()=>{expect(lineCents('1','-20','credit')).toBe(-2000);expect(lineCents('1','20','credit')).toBe(-2000);expect(lineCents('1','-20','other')).toBeNull();expect(lineCents('1','150')!+lineCents('1','-20','credit')!).toBe(13000);});
});
