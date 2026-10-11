export async function invoiceApi<T>(path:string, body?:unknown, key?:string, signal?:AbortSignal):Promise<T>{
 const r=await fetch('/api/v1/invoices'+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{'Content-Type':'application/json',...(key?{'Idempotency-Key':key}:{})},...(body===undefined?{}:{body:JSON.stringify(body)}),signal});
 if(r.status===401)window.dispatchEvent(new Event('goob-session-expired'));
 if(!r.headers.get('content-type')?.includes('application/json'))throw new Error('The invoice service is unavailable.');
 const data=await r.json();if(!r.ok)throw new Error(data.error||'Invoice request failed.');return data;
}
export type Line={description:string;quantity:string;unit_price:string|null;category:'labor'|'material'|'other'|'unclassified'|'credit';source_text:string;pricebook_id:string|null;apply_membership:boolean};
export type Draft={customer_id:string;property_id:string;job_id:string|null;equipment_id:string|null;trade:string;service:string;service_date:string;invoice_date:string;due_date:string;source_text:string;generation_source_text:string;title:string;description:string;lines:Line[];missing_information:string[];ambiguities:string[];review_note:string;review_confirmed:boolean};
export type CatalogRecord={id:string;name:string;branch_id:string;parent_id:string|null;customer_id:string|null;property_id:string|null;equipment_id:string|null;data:Record<string,unknown>};
export type Options={customers:CatalogRecord[];properties:CatalogRecord[];equipment:CatalogRecord[];jobs:CatalogRecord[];skus:CatalogRecord[]};
export type Preview={preview_token:string;lines:(Line&{subtotal_cents:number|null;total_cents:number|null;discount_cents:number;proposed_discount_cents:number;discount_percent:number;discount_reason:string})[];subtotal_cents:number;discount_cents:number;tax_cents:number|null;total_cents:number;partial:boolean;issues:string[];can_finalize:boolean;configuration:{company:{name:string;address:string;contact:string};tax_reason:string};customer:{name:string;email:string;phone:string};property:{address:string}};
export type Saved={id:string;number:string|null;status:string;revision:number;created_at:string;job_id:string|null;customer_id:string|null;snapshot:Preview&{draft?:Draft}};
export const blankLine=():Line=>({description:'',quantity:'1',unit_price:null,category:'unclassified',source_text:'',pricebook_id:null,apply_membership:false});
export const money=(c:number|null|undefined)=>c==null?'Pending':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(c/100);
export function lineCents(quantity:string,price:string|null,category?:string):number|null{
 if(price===null||!/^-?\d{1,8}(\.\d{1,2})?$/.test(price)||!/^\d{1,6}(\.\d{1,3})?$/.test(quantity))return null;
 if(price.startsWith('-')&&category!=='credit')return null;
 const [dollars,fraction='']=price.replace(/^-/, '').split('.'),[units,part='']=quantity.split('.');
 const unitCents=BigInt(dollars)*100n+BigInt(fraction.padEnd(2,'0'));
 const scale=10n**BigInt(part.length),amount=BigInt(units+part)*unitCents;
 return (category==='credit'?-1:1)*Number((amount+scale/2n)/scale);
}
