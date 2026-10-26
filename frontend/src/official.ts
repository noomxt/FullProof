/** UI adapter for official final-mentor-v11 @7998973. No client-side verdicts. */
import type {Case,Draft,Proof,System,Mapping,Scenario,Verification,VerificationRequest} from './api';
import {mappingMessage,reviewMessage,closeMessage} from './signing';
import {signedMessage} from './wallet';
import {computeIntegrity,type IntegrityData} from './integrity';
import {startVerification} from './verificationRequests';
const base=import.meta.env.VITE_API_BASE_URL||'/backend';
export async function request<T>(path:string,body?:unknown):Promise<T>{
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),150000);
 try{
  const res=await fetch(base+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
  let out;try{out=await res.json()}catch{throw Error('서버 응답을 읽을 수 없습니다. 기존 기록을 조회해 주세요.')}
  if(!res.ok||out.success===false){const detail=out.error?.message||out.detail||'API 요청 실패';throw Object.assign(Error(typeof detail==='string'?detail:JSON.stringify(detail)),{status:res.status,code:out.error?.code||'OFFICIAL_API_ERROR'})}
  return (out.success===true?out.data:out) as T;
 }catch(e){if((e as {status?:number}).status)throw e;throw Object.assign(Error(body?'응답 상태가 불명확합니다. 재전송 전에 상태 새로고침으로 기존 기록을 확인하세요.':'백엔드 연결을 확인해 주세요. frontend_server:app 및 Vite 프록시가 필요합니다.'),{code:body?'CONNECTION_UNKNOWN':'CONNECTION_ERROR',status:0})}finally{clearTimeout(timeout)}
}
const getCase=(id:string)=>request<Case>('/api/v1/frontend/cases/'+encodeURIComponent(id));
async function getConfig():Promise<System>{
 const value=await request<System>('/api/v1/frontend/status');
 if(!value.chain||!value.ai||!value.capabilities)throw Error('frontend/status 응답 구조가 화면 규격과 다릅니다. 공식 백엔드 버전을 확인해 주세요.');
 return value;
}
const time='2026-10-18T05:00:00Z';
export const scenarios:Scenario[]=['supported','contradicted','insufficient','ambiguous'].map(id=>({id,title:({supported:'정상 일치',contradicted:'결과 불일치',insufficient:'증빙 부족',ambiguous:'연결 근거 부족'} as Record<string,string>)[id],note:'가상 통신사 자료',claim_text:'2026년 10월 18일 14시에 P001과 통화에 성공했다.',result:id==='insufficient'?null:id==='contradicted'?'CALL_FAILED':'CALL_CONNECTED'}));
function scenarioClaim(c:Case){return scenarios[0].claim_text+(c.scenario_id==='ambiguous'?'':` CALL_REF[DEMO-TEL:CALL-${c.case_id}]`)}
function content(p:Proof){const keys='schema_version proof_id proof_version case_id step_id issuer_agency_id agency_address proof_type call_id target_id action_type proof_occurred_at proof_issued_at result source_sha256'.split(' ');return Object.fromEntries(keys.map(k=>[k,(p as unknown as Record<string,unknown>)[k]]))}
const drafts=new Map<string,{proof:Proof;typed_data:Draft['typed_data']}>();
let lastCase:Case|null=null;
export async function officialRequest<T>(path:string,body?:unknown):Promise<T>{
 const result=await dispatch(path,body as Record<string,unknown>|undefined);return result as T;
}
async function dispatch(path:string,b?:Record<string,unknown>):Promise<unknown>{
 if(path==='/api/v1/demo/session')return {token:'LOCAL_UI_ROLE_ONLY'}; // UI role is NOT authentication
 if(path==='/api/v1/system/status')return getConfig();
 if(path==='/api/v1/demo/scenarios')return scenarios.map(s=>({...s,claim_text:lastCase?scenarioClaim(lastCase):s.claim_text}));
 if(path==='/api/v1/cases'&&!b){const rows=await request<Case[]>('/api/v1/frontend/cases');return rows}
 if(path==='/api/v1/cases'&&b){
  const id=`FP-${b.scenario_id||'supported'}-${crypto.randomUUID().slice(0,8)}`;
  const record=await request<{case_id:string}>('/api/v1/cases',{case_id:id,title:b.title});
  try{await request('/api/v1/cases/'+id+'/steps',{step_name:'통화 사실 확인',is_required:true})}catch(e){throw Error('사건은 생성되었지만 단계 생성 응답이 불명확합니다. 사건을 열어 단계 상태를 확인하세요. '+(e as Error).message)}
  return getCase(record.case_id);
 }
 let match=path.match(/^\/api\/v1\/cases\/([^/]+)$/);
 if(match){lastCase=await getCase(match[1]);return lastCase}
 match=path.match(/^\/api\/v1\/cases\/([^/]+)\/claims$/);
 if(match&&b){const c=await getCase(match[1]),latest=c.claims.filter(x=>x.claim_id===b.claim_id).at(-1);return request(path,{claim_id:b.claim_id||'CL-'+crypto.randomUUID(),claim_version:b.claim_id?(latest?.claim_version||0)+1:1,claim_text:b.claim_text,step_id:b.step_id})}
 match=path.match(/^\/api\/v1\/claims\/([^/]+)\/extract$/);
 if(match&&b){const c=await findClaim(match[1]),claim=c.claims.find(x=>x.claim_id===match![1]&&x.claim_version===Number(b.claim_version||c.claims.at(-1)?.claim_version))!;const result=await request(path,{case_id:c.case_id,claim_version:claim.claim_version});return {...result as object,execution:{is_simulated:(await getConfig()).ai.is_simulated}}}
 if(path==='/api/v1/proofs/drafts'&&b){
  const c=await getCase(String(b.case_id)),config=await getConfig();
  if(!config.chain.agency_address||!config.chain.signer_address)throw Error('UI_AGENCY_ADDRESS와 기관 등록 지갑을 백엔드에 설정해 주세요.');
  const proofId=String(b.proof_id||'PR-'+crypto.randomUUID());
  const proof={schema_version:'1.1',proof_id:proofId,proof_version:1,case_id:c.case_id,step_id:Number(b.step_id||0),issuer_agency_id:'DEMO-TEL',agency_address:config.chain.agency_address,proof_type:'CALL_LOG',call_id:'CALL-'+c.case_id,target_id:'P001',action_type:'PHONE_CALL',proof_occurred_at:time,proof_issued_at:'2026-10-18T05:01:00Z',result:c.scenario_id==='contradicted'?'CALL_FAILED':'CALL_CONNECTED',source_sha256:'0x'+'0'.repeat(64)};
  const source=JSON.stringify({...proof,note:'가상 통신사 자료 · 실제 개인정보 없음'});
  const response=b.proof_id?await request<{proof_content:Proof;proof_hash:string;typed_data:Draft['typed_data']}>('/api/v1/frontend/drafts/'+c.case_id+'/'+proofId+'/'+String(b.proof_version||1)):await request<{proof_content:Proof;proof_hash:string;typed_data:Draft['typed_data']}>(path,{proof_content:proof,source_text:source,nonce:config.chain.agency_nonce,deadline:Math.floor(Date.now()/1000)+900});
  const p={...response.proof_content,proof_hash:response.proof_hash};drafts.set(proofId,{proof:p,typed_data:response.typed_data});
  return {draft_id:proofId,proof:p,typed_data:response.typed_data,signer_address:config.chain.signer_address,domain_warning:'기관 Proof만 서명합니다. 이후 백엔드가 거래를 제출하며, 서명 자체는 온체인 저장 완료가 아닙니다.'};
 }
 if(path==='/api/v1/proofs/anchor'&&b){
  const draft=drafts.get(String(b.draft_id));if(!draft)throw Error('현재 화면에서 생성한 서명 초안이 없습니다. 저장된 증빙을 조회해 주세요.');
  const p=draft.proof,m=draft.typed_data.message;
  return request(path,{case_id:p.case_id,step_id:p.step_id,proof_id:p.proof_id,proof_version:p.proof_version,proof_hash:p.proof_hash,occurred_at:Number(m.occurredAt),issued_at:Number(m.issuedAt),agency:m.agency,nonce:Number(m.nonce),deadline:Number(m.deadline),signature:b.signature});
 }
 match=path.match(/^\/api\/v1\/claims\/([^/]+)\/proof-mappings$/);
 if(match&&b){
  const c=await findClaim(match[1]),claim=c.claims.find(x=>x.claim_id===match![1]&&x.claim_version===b.claim_version)!,p=c.proofs.find(x=>x.proof_id===b.proof_id&&x.proof_version===b.proof_version)!;
  if(!p||!claim)throw Error('선택한 Claim·Proof 버전을 다시 조회해 주세요.');
  // Reuse a pending record after wallet rejection. Never create a duplicate CONFIRMED mapping.
  const existing=c.mappings.find(x=>x.claim_id===claim.claim_id&&x.claim_version===claim.claim_version&&x.proof_id===p.proof_id&&x.proof_version===p.proof_version&&['PENDING','CONFIRMED'].includes(x.mapping_status));
  if(existing?.mapping_status==='CONFIRMED')return existing;
  const m=existing||await request<Mapping>(path,{case_id:c.case_id,step_id:claim.step_id,claim_version:claim.claim_version,claim_text:claim.claim_text,proof_id:p.proof_id,proof_version:p.proof_version,issuer_agency_id:p.issuer_agency_id,call_id:p.call_id,mapping_method:'MANUAL_SELECTION',mapping_status:'PENDING'});
  const note=String(b.evidence_note||'선택한 통화 ID와 기관 원본을 확인하여 연결을 확정합니다.');
  const config=await getConfig();const signed=await signedMessage(config,'reviewer',()=>mappingMessage(c.case_id,m as unknown as Record<string,unknown>,claim.claim_hash,p.proof_hash,p.source_sha256,note));
  return request(path+'/'+m.mapping_id+'/confirm',{case_id:c.case_id,claim_text:claim.claim_text,evidence_source_sha256:p.source_sha256,evidence_note:note,signer_address:signed.account,signature:signed.signature});
 }
 if(path==='/api/v1/verifications'&&b){
  const c=await findClaim(String(b.claim_id)),claim=c.claims.find(x=>x.claim_id===b.claim_id&&x.claim_version===b.claim_version)!;
  const maps=c.mappings.filter(m=>m.claim_id===claim.claim_id&&m.claim_version===claim.claim_version&&m.mapping_status==='CONFIRMED');
  const proofs=c.proofs.filter(p=>maps.some(m=>m.proof_id===p.proof_id&&m.proof_version===p.proof_version));
  return startVerification(request,{claim:{case_id:c.case_id,claim_id:claim.claim_id,claim_version:claim.claim_version},proofs:proofs.map(content)});
 }
 match=path.match(/^\/api\/v1\/verifications\/([^/]+)$/);
 if(match&&!b){
  const job=await request<VerificationRequest>('/api/v1/verification-requests/'+encodeURIComponent(match[1]));
  if(job.request_state!=='CONFIRMED'||!job.result?.verification_tx_hash)throw Error('검증 요청 상태: '+job.request_state+' · 기존 요청 상태 조회에서 확인하세요.');
  return job.result;
 }
 match=path.match(/^\/api\/v1\/verifications\/([^/]+)\/reviews$/);
 if(match){
  const c=await findVerification(match[1]),v=c.verifications.find(x=>x.verification_id===match![1])!;
  if(!b)return {items:c.reviews?.filter(x=>x.verification_id===v.verification_id)||[]};
  const config=await getConfig(),data:Record<string,unknown>={review_status:b.review_status,reason_code:null,reason_text:b.reason_text,nonce:crypto.randomUUID(),deadline:Math.floor(Date.now()/1000)+900};
  const signed=await signedMessage(config,'admin',account=>{data.signer_address=account;return reviewMessage(config.chain.chain_id!,config.chain.contract_address!,v.verification_id,v.verification_hash,data)});
  return request(path,{...data,signature:signed.signature});
 }
 match=path.match(/^\/api\/v1\/cases\/([^/]+)\/close$/);
 if(match&&b){
  const config=await getConfig(),data:Record<string,unknown>={reason:b.reason_text,nonce:crypto.randomUUID(),deadline:Math.floor(Date.now()/1000)+900};
  const signed=await signedMessage(config,'admin',account=>{data.signer_address=account;return closeMessage(config.chain.chain_id!,config.chain.contract_address!,match![1],data)});
  return request(path,{...data,signature:signed.signature});
 }
 if(path==='/api/v1/blockchain/transactions'){
  const cases=await request<Case[]>('/api/v1/frontend/cases');return cases.flatMap(c=>[...c.claims.map(x=>({request_id:x.claim_tx_hash,tx_hash:x.claim_tx_hash,chain_status:x.chain_status,kind:'CLAIM'})),...c.proofs.filter(x=>x.proof_tx_hash).map(x=>({request_id:x.proof_tx_hash,tx_hash:x.proof_tx_hash,chain_status:x.chain_status,kind:'PROOF'})),...c.verifications.filter(x=>x.verification_tx_hash).map(x=>({request_id:x.verification_tx_hash,tx_hash:x.verification_tx_hash,chain_status:x.chain_status,kind:'VERIFICATION'})),...(c.reviews||[]).filter(x=>x.review_tx_hash).map(x=>({request_id:x.review_tx_hash,tx_hash:x.review_tx_hash,chain_status:x.chain_status,kind:'REVIEW'})),...(c.close_tx_hash?[{request_id:c.close_tx_hash,tx_hash:c.close_tx_hash,chain_status:'CONFIRMED',kind:'CLOSE'}]:[])]);
 }
 match=path.match(/^\/api\/v1\/blockchain\/transactions\/(.+)$/);if(match)return request('/api/v1/frontend/transactions/'+match[1]);
 if(path.endsWith('/integrity'))return computeIntegrity(await request<IntegrityData>(path+'-data'));

 return request(path,b);
}
async function findClaim(id:string){const rows=await request<Case[]>('/api/v1/frontend/cases');const c=rows.find(x=>x.claims.some(y=>y.claim_id===id));if(!c)throw Error('Claim을 찾지 못했습니다.');return c}
async function findVerification(id:string){const rows=await request<Case[]>('/api/v1/frontend/cases');const c=rows.find(x=>x.verifications.some(y=>y.verification_id===id));if(!c)throw Error('검증을 찾지 못했습니다.');return c}

