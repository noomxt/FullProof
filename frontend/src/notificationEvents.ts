import type {Case,Role} from './api';
import {caseTitle} from './presentation';
export interface WorkNotification {id:string;case_id:string;title:string;case_title:string;at:string|null;href:string;read:boolean}
export interface NotificationState {known:string[];items:WorkNotification[]}
export function notificationEvents(cases:Case[],role:Role):WorkNotification[]{
 const items:WorkNotification[]=[];
 for(const c of cases){
  const add=(id:string,title:string,at:string|null,tab:string,step:number)=>items.push({id,case_id:c.case_id,title,case_title:caseTitle(c.title),at,read:false,href:'/cases/'+encodeURIComponent(c.case_id)+'?'+new URLSearchParams({tab,step:String(step),notice:id})});
  if(role==='OFFICER'){
   for(const p of c.proofs)if(p.chain_status==='CONFIRMED')add('proof:'+c.case_id+':'+p.proof_id+':'+p.proof_version,'기관 증빙이 도착했습니다',p.proof_issued_at,'proofs',p.step_id);
   for(const r of c.reviews||[])if(r.chain_status==='CONFIRMED'&&['REVISION_REQUESTED','ACCEPTED','ACKNOWLEDGED'].includes(r.review_status))add('review:'+c.case_id+':'+r.review_id,r.review_status==='REVISION_REQUESTED'?'관리자 보완 요청이 있습니다':r.review_status==='ACCEPTED'?'관리자 단계 완료 승인이 기록됐습니다':'관리자가 검증 결과를 확인했습니다',r.reviewed_at,'history',r.step_id);
  }
  // This is an observed verification record, not an invented review-request API.
  if(role==='ADMIN')for(const v of c.verifications)if(v.chain_status==='CONFIRMED'&&v.freshness_status==='CURRENT')add('verification:'+c.case_id+':'+v.verification_id,'새 검증 기록을 확인해 주세요',v.created_at,'verification',v.step_id);
 }
 return items.sort((a,b)=>(b.at||'').localeCompare(a.at||''));
}
export function mergeNotifications(previous:NotificationState|null,events:WorkNotification[]):NotificationState{
 events=[...new Map(events.map(e=>[e.id,e])).values()];
 if(!previous)return {known:events.map(e=>e.id),items:[]}; // First successful fetch establishes baseline.
 const known=new Set(previous.known),newItems=events.filter(e=>!known.has(e.id));
 return {known:[...new Set([...previous.known,...events.map(e=>e.id)])],items:[...newItems,...previous.items].slice(0,100)};
}
