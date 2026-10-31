import {canonical} from './signing';
export interface IntegrityData {
 claim:Record<string,unknown>;proofs:{content:Record<string,unknown>;source_text:string;stored_proof_hash:string}[];
 verification:Record<string,unknown>;policy:Record<string,unknown>;chain_id:number;contract_address:string;
 onchain:{claim_hash:string|null;proofs:{proof_id:string;proof_version:number;proof_hash:string|null}[];verification:Record<string,unknown>|null};
}
export interface IntegrityCheck {name:string;status:'MATCH'|'MISMATCH'|'UNAVAILABLE';computed:string;recorded:string|null}
export interface IntegrityReport {checks:IntegrityCheck[];ok:boolean;scope:string;chain_id:number;contract_address:string}
export async function sha256(text:string){const value=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));return '0x'+[...new Uint8Array(value)].map(x=>x.toString(16).padStart(2,'0')).join('')}
const proofFields='schema_version proof_id proof_version case_id step_id issuer_agency_id agency_address proof_type call_id target_id action_type proof_occurred_at proof_issued_at result source_sha256'.split(' ');
const verificationFields='schema_version verification_id case_id step_id claim_ref proof_refs processing_status verdict conflicts missing_information reason_text evidence_refs review_required decision_policy_version policy_hash proof_refs_hash'.split(' ');
function pick(object:Record<string,unknown>,keys:string[]){return Object.fromEntries(keys.map(k=>{if(!(k in object))throw Error('원문 필드 누락: '+k);return [k,object[k]]}))}
// Python's proof ID sort is Unicode code-point order; JSON keys use JCS UTF-16 order.
function compareId(a:string,b:string){const x=Array.from(a),y=Array.from(b);for(let i=0;i<Math.min(x.length,y.length);i++){const d=x[i].codePointAt(0)!-y[i].codePointAt(0)!;if(d)return d}return x.length-y.length}
export async function computeIntegrity(data:IntegrityData):Promise<IntegrityReport>{
 const checks:IntegrityCheck[]=[];
 function check(name:string,computed:unknown,recorded:unknown){const a=String(computed),b=recorded===null||recorded===undefined?null:String(recorded);checks.push({name,computed:a,recorded:b,status:b===null?'UNAVAILABLE':a===b?'MATCH':'MISMATCH'})}
 const claimHash=await sha256(String(data.claim.claim_text));
 check('Claim 원문 SHA-256 ↔ 저장 해시',claimHash,data.claim.claim_hash);
 check('Claim 원문 SHA-256 ↔ 온체인 해시',claimHash,data.onchain.claim_hash);
 for(const p of data.proofs){
  const id=String(p.content.proof_id);const hash=await sha256(canonical(pick(p.content,proofFields)));
  check(id+' · 원천 원문 SHA-256',await sha256(p.source_text),p.content.source_sha256);
  check(id+' · Proof JCS·SHA-256 ↔ 저장 해시',hash,p.stored_proof_hash);
  check(id+' · Proof JCS·SHA-256 ↔ 온체인 해시',hash,data.onchain.proofs.find(x=>x.proof_id===id&&x.proof_version===p.content.proof_version)?.proof_hash);
 }
 const v=data.verification,ref=v.claim_ref as Record<string,unknown>,refs=v.proof_refs as {proof_id:string;proof_version:number;proof_hash:string}[];
 const sorted=[...refs].sort((a,b)=>compareId(a.proof_id,b.proof_id)||a.proof_version-b.proof_version);
 const refsHash=await sha256(canonical({schema_version:'1.1',proof_refs:sorted}));
 check('Proof 참조 목록 JCS·SHA-256',refsHash,v.proof_refs_hash);
 check('제공된 정책 원문 JCS·SHA-256',await sha256(canonical(data.policy)),v.policy_hash);
 const verificationHash=await sha256(canonical(pick(v,verificationFields)));
 check('Verification JCS·SHA-256 ↔ 저장 해시',verificationHash,v.verification_hash);
 const chain=data.onchain.verification;
 check('Verification JCS·SHA-256 ↔ 온체인 해시',verificationHash,chain?.verification_hash);
 check('검증 ID 참조',await sha256(String(v.verification_id)),chain?.verification_id_hash);
 check('Claim ID 참조',await sha256(String(ref.claim_id)),chain?.claim_id_hash);
 check('Claim 버전 참조',ref.claim_version,chain?.claim_version);
 check('검증이 참조한 Claim 해시',claimHash,chain?.claim_hash);
 check('온체인 Proof 목록 해시',refsHash,chain?.proof_refs_hash);
 check('온체인 정책 해시',v.policy_hash,chain?.policy_hash);
 check('온체인 판정',v.verdict,chain?.verdict);
 for(const r of refs){const p=data.proofs.find(p=>p.content.proof_id===r.proof_id&&p.content.proof_version===r.proof_version);check(r.proof_id+' · Verification의 Proof 참조',p?await sha256(canonical(pick(p.content,proofFields))):'원문 없음',r.proof_hash)}
 return {checks,ok:checks.every(c=>c.status==='MATCH'),chain_id:data.chain_id,contract_address:data.contract_address,scope:'이 브라우저에서 받은 원문을 다시 해시하고, 서버가 현재 로컬 체인에서 조회한 기록과 대조했습니다. 판정의 사실성·기관 자료의 진실성이나 독립 RPC 감사까지 증명하지 않습니다.'};
}
