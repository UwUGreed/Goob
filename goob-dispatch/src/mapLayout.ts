export type ScreenRect={x:number;y:number;width:number;height:number};
export type ScreenLabel={id:string;anchor:{x:number;y:number};width:number;height:number;priority:number;above:boolean};
export type PlacedLabel=ScreenLabel & ScreenRect;
export const overlaps=(a:ScreenRect,b:ScreenRect,gap=5)=>a.x<b.x+b.width+gap&&a.x+a.width+gap>b.x&&a.y<b.y+b.height+gap&&a.y+a.height+gap>b.y;
export function layoutLabels(labels:ScreenLabel[],width:number,height:number,reserved:ScreenRect[]):PlacedLabel[]{
  const placed:PlacedLabel[]=[],occupied=[...reserved],padding=12;
  for(const label of [...labels].sort((a,b)=>b.priority-a.priority)){
    const {anchor,width:w,height:h}=label;
    const clamp=(x:number,y:number):ScreenRect=>({x:Math.max(padding,Math.min(width-w-padding,x)),y:Math.max(padding,Math.min(height-h-padding,y)),width:w,height:h});
    const preferred=label.above?anchor.y-h-23:anchor.y+17,candidates:ScreenRect[]=[];
    for(const dy of[0,label.above?h+44:-h-44,-h-38,h+38,-2*h-52,2*h+52])for(const dx of[0,w*.62,-w*.62,w+12,-w-12])candidates.push(clamp(anchor.x-w/2+dx,preferred+dy));
    for(let y=padding;y<=height-h-padding;y+=h+9)for(let x=padding;x<=width-w-padding;x+=Math.max(28,w/2))candidates.push(clamp(x,y));
    const free=candidates.filter(c=>!occupied.some(r=>overlaps(c,r)));
    free.sort((a,b)=>Math.hypot(a.x+w/2-anchor.x,a.y+h/2-anchor.y)-Math.hypot(b.x+w/2-anchor.x,b.y+h/2-anchor.y));
    const rect=free[0];if(!rect)continue;const result={...label,...rect};placed.push(result);occupied.push(rect);
  }return placed;
}
