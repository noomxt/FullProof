import { cases, claims } from '../data/mock';
import type { Claim, Comparison, FullProofApi, Verification } from '../types';
const key='fullproof-demo-history-v1';
let memory:Verification[]=[];
try { memory=JSON.parse(localStorage.getItem(key)||'[]'); if(!Array.isArray(memory)) memory=[]; } catch { memory=[]; }
const persist=()=>{try{localStorage.setItem(key,JSON.stringify(memory));}catch{/* Session memory remains usable. */}};
const delay=()=>new Promise(r=>setTimeout(r,450));
export function compare(claim:Claim):Omit<Verification,'id'|'createdAt'|'chain'> {
 const p=claim.proof;
 const pairs=[['행위 단계',claim.stage,p?.stage],['장소',claim.location,p?.location],['시간',claim.time,p?.time],['사건 식별자',claim.caseId,p?.caseId]];
 const comparisons:Comparison[]=pairs.map(([field,a,b])=>({field:field!,claim:a!,proof:b||'증빙 없음',status:!b?'확인 불가':a===b?'일치':field==='행위 단계'?'확인 불가':'불일치'}));
 const verdict=!p?'검증 보류':comparisons.some(x=>x.status==='불일치')?'불일치':claim.stage!==p.stage?'추가 확인':'일치';
 return {claimId:claim.id,caseId:claim.caseId,demo:true,comparisons,verdict,rationale:!p?'독립적인 원천기관 증빙이 없어 이행 여부를 확인할 수 없습니다.':claim.stage!==p.stage?'자료 제공 로그는 제공 단계만 증빙합니다. 실제 영상 열람을 확인할 독립적인 열람 로그가 없습니다.':verdict==='불일치'?'Claim과 제공 로그의 장소 또는 시간이 다릅니다. 기록 오류인지 확인이 필요하며 허위 기록으로 단정하지 않습니다.':`${claim.stage} 단계의 장소·시간·사건 식별자가 시연용 증빙과 일치합니다. 다른 행위 단계나 수사 결과까지 입증하는 것은 아닙니다.`,nextAction:verdict==='일치'?'담당자가 증빙 범위를 검토해 주세요.':verdict==='추가 확인'?'열람 일시와 사용자 식별자가 포함된 독립적인 열람 감사 로그를 확보해 주세요.':verdict==='검증 보류'?'원천기관의 요청 접수 또는 해당 행위 증빙을 확보해 주세요.':'원본 기록과 기관 제공 로그를 담당자가 다시 확인해 주세요.'};
}
export const mockApi:FullProofApi={
 async cases(){await delay();return structuredClone(cases)},async claims(id){await delay();return structuredClone(claims.filter(c=>c.caseId===id))},async claim(id){await delay();return structuredClone(claims.find(c=>c.id===id)||null)},
 async verify(id,fail=false){await delay();if(fail)throw new Error('시연용 검증 요청 실패입니다. 다시 시도해 주세요.');const c=claims.find(c=>c.id===id);if(!c)throw new Error('Claim을 찾을 수 없습니다.');const v:Verification={...compare(c),id:crypto.randomUUID(),createdAt:new Date().toISOString(),chain:{status:'미연결',transactionHash:null,recordHash:null}};memory=[v,...memory];persist();return structuredClone(v)},
 async history(){await delay();return structuredClone(memory)},async queue(id,fail=false){await delay();const v=memory.find(v=>v.id===id);if(!v)throw new Error('검증 기록을 찾을 수 없습니다.');v.chain.status=fail?'저장 실패':'저장 대기';const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify({id:v.id,claimId:v.claimId,createdAt:v.createdAt,verdict:v.verdict,comparisons:v.comparisons})));v.chain.recordHash=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');persist();return structuredClone(v)},async reset(){memory=[];persist()}
};
