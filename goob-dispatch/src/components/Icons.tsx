import { Droplets, Fan, Zap } from 'lucide-react';
import { tradeColors } from '../data';
import type { Trade } from '../types';
export function TradeIcon({trade,size=18,bubble=false}:{trade:Trade;size?:number;bubble?:boolean}) {
  const Icon=trade==='Plumbing'?Droplets:trade==='HVAC'?Fan:Zap;
  return <span className={bubble?'trade-bubble':'trade-symbol'} style={{color:tradeColors[trade],background:bubble?`${tradeColors[trade]}18`:undefined}}><Icon size={size} strokeWidth={2.2}/></span>;
}
