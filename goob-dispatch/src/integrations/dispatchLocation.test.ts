import {describe,it,expect} from 'vitest';
import {validMapPoint,realStops} from './geography';
describe('Dispatch missing coordinates regression',()=>{
 it('rejects absent job locations before marker projection or lat/lng access',()=>{
  expect(validMapPoint(realStops['2-2'])).toBe(false);
  expect(validMapPoint(realStops.unknown)).toBe(false);
  expect(validMapPoint(undefined)).toBe(false);
  expect(validMapPoint({lat:NaN,lng:0})).toBe(false);
  expect(validMapPoint({lat:34,lng:-81})).toBe(true);
 });
});
