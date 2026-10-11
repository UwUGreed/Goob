import { describe, expect, it } from 'vitest';
import { geoPosition, heading, meters, decodePolyline } from './geography';
describe('geographic route interpolation',()=>{
  it('interpolates cumulative road-segment distance instead of taking a diagonal shortcut',()=>{
    const route=[{lat:34,lng:-81.04},{lat:34.001,lng:-81.04},{lat:34.001,lng:-81.038}];const first=meters(route[0],route[1]),total=first+meters(route[1],route[2]);
    const onFirst=geoPosition(route,first/total/2);expect(onFirst.lng).toBe(-81.04);expect(onFirst.lat).toBeCloseTo(34.0005,5);expect(onFirst.heading).toBeCloseTo(0,1);
    const onSecond=geoPosition(route,(first+(total-first)/2)/total);expect(onSecond.lat).toBe(34.001);expect(onSecond.lng).toBeCloseTo(-81.039,5);expect(onSecond.heading).toBeCloseTo(90,1);
    expect(geoPosition(route,1)).toMatchObject(route[2]);expect(heading(route[1],route[0])).toBeCloseTo(180);
  });
  it('rejects malformed route encodings',()=>{expect(()=>decodePolyline('~')).toThrow();expect(()=>decodePolyline('\u0000')).toThrow();expect(decodePolyline('??')).toEqual([{lat:0,lng:0}]);});
});
