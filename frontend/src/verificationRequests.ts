import type {Verification,VerificationRequest} from './api';

type Transport=<T>(path:string,body?:unknown)=>Promise<T>;
export interface VerificationInput {claim:{case_id:string;claim_id:string;claim_version:number};proofs:Record<string,unknown>[]}
const prefix='fullproof.verification.pending.v2:';
const key=(input:VerificationInput)=>prefix+JSON.stringify(input.claim);
const knownStates=['PROCESSING','SUBMITTED','CONFIRMED','FAILED','UNKNOWN'];
export function publishRequest(job:VerificationRequest){window.dispatchEvent(new CustomEvent('fullproof:verification-request',{detail:job}))}
function validate(job:VerificationRequest){
 if(!job?.verification_id||!job.case_id||!knownStates.includes(job.request_state))throw Object.assign(Error('검증 요청 응답 형식을 확인할 수 없습니다. 사건의 검증 이력을 조회하세요.'),{code:'REQUEST_SCHEMA_ERROR'});
 return job;
}
function clearPending(id:string){
 for(const name of Object.keys(localStorage).filter(k=>k.startsWith(prefix))){
  try{if(JSON.parse(localStorage.getItem(name)!).verification_id===id)localStorage.removeItem(name)}catch{/* Unreadable entries never trigger a POST. */}
 }
}
export async function waitForVerification(send:Transport,initial:VerificationRequest):Promise<Verification>{
 let job=validate(initial);
 for(let attempt=0;attempt<90;attempt++){
  publishRequest(job);
  if(job.request_state==='CONFIRMED'){
   if(!job.result?.verification_tx_hash||job.result.verification_id!==job.verification_id)throw Object.assign(Error('서버 완료 응답과 거래 기록이 일치하지 않습니다. 기존 요청 상태를 확인하세요.'),{code:'REQUEST_RESULT_MISMATCH'});
   clearPending(job.verification_id);
   return job.result;
  }
  if(job.request_state==='FAILED'){
   clearPending(job.verification_id);
   throw Object.assign(Error(job.error||'검증 처리에 실패했습니다. 원인과 기존 요청을 확인한 후 다시 실행하세요.'),{code:'VERIFICATION_FAILED'});
  }
  if(job.request_state==='UNKNOWN')throw Object.assign(Error(job.error||'거래 처리 상태를 확인해야 합니다. 재제출하지 말고 기존 요청 상태를 다시 조회하세요.'),{code:'VERIFICATION_UNKNOWN'});
  await new Promise(resolve=>setTimeout(resolve,1000));
  const next=validate(await send<VerificationRequest>('/api/v1/verification-requests/'+encodeURIComponent(job.verification_id)));
  if(next.verification_id!==job.verification_id||next.case_id!==job.case_id)throw Object.assign(Error('조회한 검증 요청 ID가 다릅니다.'),{code:'REQUEST_ID_MISMATCH'});
  job=next;
 }
 throw Object.assign(Error('검증이 계속 처리 중입니다. 요청 ID는 보관했습니다. 기존 요청 상태 조회로 이어서 확인하세요.'),{code:'VERIFICATION_PENDING',status:202});
}
export async function startVerification(send:Transport,input:VerificationInput):Promise<Verification>{
 const saved=localStorage.getItem(key(input));
 if(saved){
  let prior:{verification_id:string;input:string};
  try{prior=JSON.parse(saved);if(!prior.verification_id)throw Error()}catch{throw Error('저장된 검증 요청 정보를 읽을 수 없습니다. 사건의 기존 요청 상태부터 확인하세요.')}
  const job=validate(await send<VerificationRequest>('/api/v1/verification-requests/'+encodeURIComponent(prior.verification_id)));
  if(job.case_id!==input.claim.case_id)throw Error('저장된 검증 요청의 사건이 다릅니다. 기존 기록을 확인하세요.');
  const result=await waitForVerification(send,job);
  if(prior.input!==JSON.stringify(input))throw Error('이전 검증 완료를 확인했습니다. 현재 Claim·Proof 선택을 확인한 뒤 새 검증을 실행하세요.');
  return result;
 }
 // Backend owns IDs, input fingerprints, durable jobs and all retry/chain rules.
 const job=validate(await send<VerificationRequest>('/api/v1/verification-requests',input));
 if(job.case_id!==input.claim.case_id)throw Error('생성된 검증 요청의 사건이 다릅니다. 기존 기록을 확인하세요.');
 localStorage.setItem(key(input),JSON.stringify({verification_id:job.verification_id,input:JSON.stringify(input)}));
 return waitForVerification(send,job);
}
