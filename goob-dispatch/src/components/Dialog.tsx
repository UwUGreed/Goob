import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
export function Dialog({title,onClose,children,className=''}:{title:string;onClose:()=>void;children:React.ReactNode;className?:string}) {
  const ref=useRef<HTMLDivElement>(null),close=useRef(onClose);close.current=onClose;
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement;ref.current?.querySelector<HTMLElement>('button')?.focus();
    const key=(e:KeyboardEvent)=>{
      if(e.key==='Escape')close.current();
      if(e.key==='Tab') {const items=Array.from(ref.current!.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),a[href],summary'));const first=items[0],last=items.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}
    };document.addEventListener('keydown',key);return ()=>{document.removeEventListener('keydown',key);previous?.focus();};
  },[]);
  return <div className="dialog-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div ref={ref} className={`dialog ${className}`} role="dialog" aria-modal="true" aria-label={title}><div className="dialog-header"><h2>{title}</h2><button onClick={onClose} aria-label="Close dialog"><X size={20}/></button></div>{children}</div></div>;
}
