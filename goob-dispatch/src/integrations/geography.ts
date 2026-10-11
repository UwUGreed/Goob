export type GeoPoint = {lat:number;lng:number};
export type DrivingRoute = {coordinates:GeoPoint[];distanceMeters:number;durationSeconds:number;origin:GeoPoint;destination:GeoPoint;source:'google'};
export const columbia:GeoPoint={lat:34.00125,lng:-81.0353};
// Independently verified City of Columbia GIS road-centerline intersections.
// Customers, depot operations, street aliases, visits, and technicians are fictional.
export const realStops:Record<string,GeoPoint & {label:string}>={
  '0-3':{lat:33.99974301276479,lng:-81.03854638217868,label:'Lincoln St / Gervais St'},
  '3-2':{lat:34.00157289674873,lng:-81.03747477705934,label:'Park St / Lady St'},
  '1-0':{lat:34.002610010891665,lng:-81.03413401018938,label:'Main St / Lady St'},
  '3-1':{lat:34.00176596795156,lng:-81.03193725889034,label:'Sumter St / Gervais St'},
  '1-1':{lat:34.00025168125426,lng:-81.0368938050366,label:'Park St / Gervais St'},
};
export function meters(a:GeoPoint,b:GeoPoint){const r=Math.PI/180,dLat=(b.lat-a.lat)*r,dLng=(b.lng-a.lng)*r,h=Math.sin(dLat/2)**2+Math.cos(a.lat*r)*Math.cos(b.lat*r)*Math.sin(dLng/2)**2;return 6371000*2*Math.atan2(Math.sqrt(h),Math.sqrt(Math.max(0,1-h)));}
export function heading(a:GeoPoint,b:GeoPoint){const r=Math.PI/180,d=(b.lng-a.lng)*r;return(Math.atan2(Math.sin(d)*Math.cos(b.lat*r),Math.cos(a.lat*r)*Math.sin(b.lat*r)-Math.sin(a.lat*r)*Math.cos(b.lat*r)*Math.cos(d))/r+360)%360;}
export function geoPosition(route:GeoPoint[],progress:number):GeoPoint & {heading:number}{
  if(route.length<2)return{...(route[0]??columbia),heading:0};
  const lengths=route.slice(1).map((p,i)=>meters(route[i],p));let remaining=lengths.reduce((a,b)=>a+b,0)*Math.max(0,Math.min(1,progress));
  for(let i=1;i<route.length;i++){const length=lengths[i-1];if(remaining<=length||i===route.length-1){const f=length?Math.min(1,remaining/length):0,a=route[i-1],b=route[i];return{lat:a.lat+(b.lat-a.lat)*f,lng:a.lng+(b.lng-a.lng)*f,heading:heading(a,b)};}remaining-=length;}
  return{...route.at(-1)!,heading:0};
}
export function decodePolyline(encoded:string):GeoPoint[]{
  const result:GeoPoint[]=[];let index=0,lat=0,lng=0;
  const read=()=>{let value=0,shift=0,byte:number;do{if(index>=encoded.length||shift>30)throw new Error('Invalid route polyline');byte=encoded.charCodeAt(index++)-63;if(byte<0||byte>63)throw new Error('Invalid route polyline');value|=(byte&31)<<shift;shift+=5;}while(byte>=32);return(value&1)?~(value>>1):value>>1;};
  while(index<encoded.length){lat+=read();lng+=read();const point={lat:lat/1e5,lng:lng/1e5};if(Math.abs(point.lat)>90||Math.abs(point.lng)>180)throw new Error('Invalid route coordinates');result.push(point);if(result.length>20000)throw new Error('Route is too complex');}return result;
}
