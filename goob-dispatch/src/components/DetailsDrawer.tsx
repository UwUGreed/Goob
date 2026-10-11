import { useEffect, useRef, useState, type ReactNode } from 'react';
import { X } from 'lucide-react';
export function DetailsDrawer({open,onClose,children}:{open:boolean;onClose:()=>void;children:ReactNode}){
  const host=useRef<HTMLDivElement>(null),[mobile,setMobile]=useState(()=>matchMedia('(max-width: 1120px)').matches);
  useEffect(()=>{const media=matchMedia('(max-width: 1120px)'),change=()=>setMobile(media.matches);media.addEventListener('change',change);return()=>media.removeEventListener('change',change);},[]);
  useEffect(()=>{
    if(!mobile||!open)return;
    const previous=document.activeElement as HTMLElement,overflow=document.body.style.overflow;document.body.style.overflow='hidden';
    const focusable=()=>Array.from(host.current!.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input,select,textarea,[tabindex="0"]')).filter(el=>el.getClientRects().length);
    focusable()[0]?.focus();
    const key=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();onClose();}if(event.key==='Tab'){const list=focusable(),first=list[0],last=list[list.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}}};
    document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);document.body.style.overflow=overflow;previous?.focus();};
  },[mobile,open,onClose]);
  return <>{mobile&&open&&<div className="details-backdrop" onClick={onClose} aria-hidden="true"/>}<div ref={host} className={`details-slot ${open?'drawer-open':''}`} role={mobile&&open?'dialog':undefined} aria-modal={mobile&&open?true:undefined} aria-label={mobile&&open?'Visit details':undefined}><div className="drawer-heading"><strong>Dispatch details</strong><button aria-label="Close visit details" onClick={onClose}><X size={20}/></button></div>{children}</div></>;
}
