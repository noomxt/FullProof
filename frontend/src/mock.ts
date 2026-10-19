/** Browser-only fixtures. No network, AI, wallet or blockchain operations. */
import type {Case,Claim,Proof,Verification,Role,Review,Transaction,Draft,Scenario} from './api';
const KEY='fullproof.frontend.mock.v1.1';
type State={cases:Case[];reviews:Review[];transactions:Transaction[];drafts:Record<string,string>;failure:'none'|'error'|'unknown';requests:Record<string,Verification>};
let role:Role='OFFICER',latency=350;
const stamp=()=>new Date().toISOString().replace(/\.\d{3}Z$/,'Z');
const id=(p:string)=>p+'-'+crypto.randomUUID();
export class MockError extends Error{constructor(public code:string,message:string,public status=409){super(message)}}
export const scenarios:Scenario[]=[
 {id:'supported',title:'정상 일치',note:'통화 연결 성공 증빙',claim_text:'2026년 10월 18일 14시에 P001과 통화에 성공했다.',result:'CALL_CONNECTED'},
 {id:'contradicted',title:'결과 불일치',note:'성공 주장과 연결 실패 증빙',claim_text:'2026년 10월 18일 14시에 P001과 통화에 성공했다.',result:'CALL_FAILED'},
 {id:'insufficient',title:'증빙 부족',note:'기관 Proof 미확보',claim_text:'2026년 10월 18일 14시에 P001과 통화에 성공했다.',result:null},
 {id:'ambiguous',title:'연결 불명확',note:'두 통화 중 동일 행위 확인 불가',claim_text:'2026년 10월 18일 14시에 P001과 통화에 성공했다.',result:'CALL_CONNECTED'}];
function seed():State{return {cases:scenarios.map((s,i)=>({case_id:'DEMO-2026-'+String(i+1).padStart(3,'0'),title:['가상 실종 사건 · 안산 중앙','가상 실종 사건 · 수원 영통','가상 실종 사건 · 성남 분당','가상 실종 사건 · 안양 동안'][i],region:['안산','수원','성남','안양'][i],scenario_id:s.id,status:'OPEN',created_at:stamp(),claims:[],proofs:[],verifications:[],mappings:[],reviews:[],close_eligible:false,close_blockers:['CLAIM_NOT_ANCHORED'],is_simulated:true})),reviews:[],transactions:[],drafts:{},failure:'none',requests:{}}}
let memory:State|undefined;
function state(){if(!memory){try{memory=JSON.parse(localStorage.getItem(KEY)||'null')||seed()}catch{memory=seed()}}return memory!}
function save(){try{localStorage.setItem(KEY,JSON.stringify(state()))}catch{throw new MockError('STORAGE_UNAVAILABLE','브라우저 시연 데이터를 저장할 공간이 없습니다.',503)}}
export function resetMock(){memory=seed();save()}
export function setMockLatency(ms:number){latency=ms}
export function setMockFailure(value:State['failure']){state().failure=value;save()}
const copy=<T,>(v:T):T=>JSON.parse(JSON.stringify(v));
async function hash(v:unknown){const bytes=new TextEncoder().encode(typeof v==='string'?v:JSON.stringify(v));return '0x'+[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('')}
function allow(...roles:Role[]){if(!roles.includes(role))throw new MockError('ROLE_NOT_ALLOWED','해당 시연 역할에서 실행하세요.',403)}
function getCase(cid:string){const c=state().cases.find(c=>c.case_id===cid);if(!c)throw new MockError('CASE_NOT_FOUND','사건이 없습니다.',404);return c}
function open(c:Case){if(c.status!=='OPEN')throw new MockError('CASE_ALREADY_CLOSED','종결된 사건은 수정할 수 없습니다.')}
function claim(cid:string){const c=state().cases.find(c=>c.claims.some(cl=>cl.claim_id===cid));if(!c)throw new MockError('CLAIM_NOT_FOUND','Claim이 없습니다.',404);return {c,cl:c.claims.filter(cl=>cl.claim_id===cid).at(-1)!}}
function stale(c:Case){c.verifications.forEach(v=>v.freshness_status='NEEDS_REVERIFICATION');c.close_eligible=false}
function tx(kind:string):Transaction{const t:Transaction={request_id:id('MOCK-REQUEST'),kind,chain_status:'MOCK',tx_hash:null,error_code:null,is_simulated:true};state().transactions.push(t);return t}
function blockers(c:Case){const b:string[]=[];const cl=c.claims.at(-1),v=c.verifications.at(-1);if(c.status!=='OPEN')b.push('CASE_ALREADY_CLOSED');if(!cl)b.push('CLAIM_NOT_ANCHORED');if(!v)b.push('VERIFICATION_PENDING');else{if(v.claim_ref.claim_id!==cl?.claim_id||v.claim_ref.claim_version!==cl?.claim_version||v.freshness_status!=='CURRENT')b.push('NEEDS_REVERIFICATION');if(v.verdict==='CONTRADICTED')b.push('VERIFICATION_CONTRADICTED');if(v.verdict==='INSUFFICIENT')b.push('VERIFICATION_INSUFFICIENT');if(!v.proof_refs.length)b.push('PROOF_MISSING');const review=state().reviews.filter(r=>r.verification_id===v.verification_id).at(-1);if(!review)b.push('ADMIN_REVIEW_PENDING');else if(review.review_status!=='ACCEPTED')b.push('ADMIN_REVIEW_NOT_ACCEPTED')}
 return [...new Set(b)]}
function detail(c:Case){return {...c,reviews:state().reviews.filter(r=>r.case_id===c.case_id),close_blockers:blockers(c),close_eligible:blockers(c).length===0}}
function bad(code:string,message:string,status=409):never{throw new MockError(code,message,status)}
export async function mockRequest<T>(path:string,body?:unknown):Promise<T>{
 if(latency)await new Promise(r=>setTimeout(r,latency));
 const value=await dispatch(path,body as Record<string,unknown>|undefined);save();return copy(value) as T;
}
async function dispatch(path:string,b?:Record<string,unknown>):Promise<unknown>{
 const s=state();
 if(path==='/api/v1/demo/session'){role=b!.role as Role;return {token:'frontend-mock-'+role}}
 if(path==='/api/v1/system/status')return {schema_version:'1.1',environment:'FRONTEND_MOCK',chain:{available:false},ai:{provider:'frontend-mock',is_simulated:true,key_configured:false},capabilities:{claim_anchor:true,proof_attestation:true,verification_anchor:true,admin_review:true,close_case:true},limitations:['브라우저 Mock 전용 · AI·MetaMask·블록체인 호출 없음']};
 if(path==='/api/v1/demo/scenarios')return scenarios;
 if(b&&s.failure!=='none'){
  const f=s.failure;s.failure='none';
  if(f==='unknown'){const t=tx('MOCK_UNCERTAIN');t.chain_status='UNKNOWN';t.error_code='SIMULATED_TIMEOUT';save();bad('MOCK_STATUS_UNKNOWN','가상 응답 지연입니다. 실제 거래는 없습니다. 검증·기록 이력에서 가상 요청 상태를 조회하세요.',503)}
  save();bad('MOCK_REQUEST_FAILED','의도적으로 발생시킨 시연 오류입니다. 같은 작업을 다시 시도하세요.',503)
 }
 if(path==='/api/v1/cases'){
  if(!b)return s.cases.map(detail);allow('OFFICER');const scenario=String(b.scenario_id);if(!scenarios.some(x=>x.id===scenario))bad('INVALID_SCENARIO','시연 유형을 확인하세요.',422);
  const c:Case={case_id:id('DEMO'),title:String(b.title),region:'가상 지역',scenario_id:scenario,status:'OPEN',created_at:stamp(),claims:[],proofs:[],verifications:[],mappings:[],reviews:[],close_eligible:false,close_blockers:[],is_simulated:true};s.cases.push(c);return detail(c);
 }
 if(path==='/api/v1/blockchain/transactions')return s.transactions;
 const transaction=path.match(/^\/api\/v1\/blockchain\/transactions\/(.+)$/);
 if(transaction){const t=s.transactions.find(t=>t.request_id===transaction[1]);if(!t)bad('TRANSACTION_NOT_FOUND','가상 요청이 없습니다.',404);if(t.chain_status==='UNKNOWN'){t.chain_status='MOCK';t.error_code=null}return t}
 const casePath=path.match(/^\/api\/v1\/cases\/([^/]+)(?:\/(.+))?$/);
 if(casePath){const c=getCase(casePath[1]),part=casePath[2];
  if(!part)return detail(c);
  if(part==='claims'){
   if(!b)return c.claims;allow('OFFICER');open(c);const text=String(b.claim_text||'');if(!text.trim())bad('EMPTY_CLAIM','원문을 입력하세요.',422);
   const prev=b.claim_id?c.claims.filter(cl=>cl.claim_id===b.claim_id).at(-1):undefined;
   if(b.claim_id&&!prev)bad('REFERENCE_MISMATCH','Claim 참조가 다릅니다.',422);
   const t=tx('CLAIM'),cl:Claim={claim_id:prev?.claim_id||id('MOCK-CLAIM'),claim_version:(prev?.claim_version||0)+1,case_id:c.case_id,step_id:0,claim_text:text,claim_created_at:stamp(),claimed_occurred_at:null,claim_hash:await hash(text),claim_tx_hash:null,chain_status:'MOCK',request_id:t.request_id,structured_claim:null};stale(c);c.claims.push(cl);return cl;
  }
  if(part==='proofs')return c.proofs;
  if(part==='verifications')return c.verifications;
  if(part==='chain-status')return {is_simulated:true,onchain_written:false,claims:c.claims.length,proofs:c.proofs.filter(p=>p.chain_status==='MOCK').length,verifications:c.verifications.length,notice:'브라우저 가상 기록 수 · 실제 온체인 조회 아님'};
  if(part==='close'){
   allow('ADMIN');const why=blockers(c);if(why.length)bad('CLOSE_BLOCKED',why.join(', '));if(!String(b?.reason_text||'').trim())bad('REASON_REQUIRED','종결 사유를 입력하세요.',422);
   c.status='CLOSED';c.closed_at=stamp();c.close_reason=String(b!.reason_text);c.close_request_id=tx('CASE_CLOSE').request_id;return detail(c);
  }
 }
 const claimPath=path.match(/^\/api\/v1\/claims\/([^/]+)\/(.+)$/);
 if(claimPath){const {c,cl}=claim(claimPath[1]),part=claimPath[2];
  if(part==='extract'){
   allow('OFFICER');open(c);const fixture=scenarios.find(x=>x.id===c.scenario_id)!;
   // Deliberately only accept advertised fixture text; this is not an AI parser.
   const multi=cl.claim_text===fixture.claim_text+' 그리고 CCTV를 열람했다.';
   if(cl.claim_text!==fixture.claim_text&&!multi)bad('MOCK_FIXTURE_ONLY','Mock은 제공된 시연 원문만 지원합니다. 자유 입력 분석은 실제 API 모드를 사용하세요.',422);
   const a={action_type:'PHONE_CALL',action_result:'SUCCESS',target_id:'P001',occurred_at:'2026-10-18T05:00:00Z',source_excerpt:fixture.claim_text};
   cl.structured_claim={extraction_status:multi?'NEEDS_REVIEW':'COMPLETED',actions:multi?[a,{...a,action_type:'CCTV_REVIEW',source_excerpt:'CCTV를 열람했다.'}]:[a],model_name:'FRONTEND_FIXED_FIXTURE',prompt_version:'mock-fixture-v1.1',review_required:multi};cl.claimed_occurred_at=a.occurred_at;stale(c);return {extraction:cl.structured_claim,execution:{is_simulated:true,provider:'frontend-mock'}};
  }
  if(part==='proof-candidates')return c.proofs;
  if(part==='proof-mappings'){
   allow('OFFICER');open(c);if(b?.claim_version!==cl.claim_version)bad('STALE_CLAIM','최신 Claim을 선택하세요.');
   const p=c.proofs.find(p=>p.proof_id===b?.proof_id&&p.proof_version===b?.proof_version);if(!p||p.chain_status!=='MOCK')bad('PROOF_NOT_READY','가상 기관 서명을 먼저 실행하세요.');
   c.mappings.forEach(m=>{if(m.claim_id===cl.claim_id&&m.claim_version===cl.claim_version)m.mapping_status='REJECTED'});stale(c);
   const m={mapping_id:id('MOCK-MAP'),claim_id:cl.claim_id,claim_version:cl.claim_version,proof_id:p.proof_id,proof_version:p.proof_version,mapping_status:'CONFIRMED',evidence_note:c.scenario_id==='ambiguous'||p.call_id.endsWith('02')?'연결 근거 부족 · 가상 자료':'가상 발신 요청 연결 확인',confirmed_at:stamp()};c.mappings.push(m);return m;
  }
 }
 if(path==='/api/v1/proofs/drafts'){
  allow('AGENCY');const c=getCase(String(b!.case_id));open(c);if(c.scenario_id==='insufficient')bad('PROOF_MISSING','가상 기관 증빙이 없는 사례입니다.');
  let p=c.proofs.find(p=>p.proof_id===b!.proof_id);
  if(!p){if(b!.proof_id)bad('PROOF_NOT_FOUND','Proof를 찾을 수 없습니다.',404);
   for(let i=1;i<=2;i++){const source={call_id:'MOCK-CALL-'+i.toString().padStart(2,'0'),target_id:'P001',occurred_at:i===1?'2026-10-18T05:00:00Z':'2026-10-18T05:05:00Z',result:i===1&&c.scenario_id!=='contradicted'?'CALL_CONNECTED':'CALL_FAILED',is_simulated:true};
    const raw=JSON.stringify(source);c.proofs.push({proof_id:id('MOCK-PROOF'),proof_version:1,case_id:c.case_id,step_id:0,call_id:source.call_id,issuer_agency_id:'MOCK-TELECOM',agency_address:'0x0000000000000000000000000000000000000001',action_type:'PHONE_CALL',target_id:'P001',result:source.result,proof_occurred_at:source.occurred_at,proof_issued_at:'2026-10-18T05:30:00Z',source_sha256:await hash(raw),source_uri:'mock://browser',source_bytes:raw,proof_hash:await hash(source),proof_tx_hash:null,chain_status:'PENDING',signature:null,mapping_reference:'브라우저 가상 자료'});
   }p=c.proofs.at(-2)!;
  }
  if(p.chain_status==='MOCK')bad('ALREADY_RECORDED','이미 가상 서명한 Proof입니다.');
  const did=id('MOCK-DRAFT');s.drafts[did]=p.proof_id;
  return {draft_id:did,proof:p,signer_address:p.agency_address,typed_data:{domain:{name:'MOCK_NO_SIGNATURE',version:'0',chainId:0,verifyingContract:p.agency_address},types:{},primaryType:'MockOnly',message:{}},domain_warning:'서명·거래가 없는 프론트엔드 가상 시연입니다.'} satisfies Draft;
 }
 if(path==='/api/v1/proofs/anchor'){
  allow('AGENCY');const pid=s.drafts[String(b!.draft_id)];const c=s.cases.find(c=>c.proofs.some(p=>p.proof_id===pid));if(!c)bad('DRAFT_NOT_FOUND','가상 서명 초안을 먼저 생성하세요.',404);open(c);
  const p=c.proofs.find(p=>p.proof_id===pid)!;if(p.chain_status!=='MOCK'){p.chain_status='MOCK';p.request_id=tx('PROOF').request_id;stale(c)}return p;
 }
 if(path==='/api/v1/verifications'){
  allow('OFFICER');const request=String(b!.request_id);if(s.requests[request])return s.requests[request];
  const {c,cl}=claim(String(b!.claim_id));open(c);if(cl.claim_version!==b!.claim_version||c.claims.at(-1)!==cl)bad('STALE_CLAIM','최신 Claim으로 검증하세요.');if(!cl.structured_claim)bad('EXTRACTION_REQUIRED','AI 추출 시연을 먼저 실행하세요.');
  const m=[...c.mappings].reverse().find(m=>m.claim_id===cl.claim_id&&m.claim_version===cl.claim_version&&m.mapping_status==='CONFIRMED');const p=c.proofs.find(p=>p.proof_id===m?.proof_id);
  const insufficient=!p||c.scenario_id==='ambiguous'||p.call_id.endsWith('02')||cl.structured_claim.review_required;
  const verdict=insufficient?'INSUFFICIENT':p.result==='CALL_FAILED'?'CONTRADICTED':'SUPPORTED';
  const t=tx('VERIFICATION'),v:Verification={verification_id:id('MOCK-VERIFY'),case_id:c.case_id,step_id:0,claim_ref:{claim_id:cl.claim_id,claim_version:cl.claim_version,claim_hash:cl.claim_hash},proof_refs:p?[{proof_id:p.proof_id,proof_version:p.proof_version,proof_hash:p.proof_hash}]:[],processing_status:cl.structured_claim.review_required?'NEEDS_REVIEW':'COMPLETED',verdict,conflicts:verdict==='CONTRADICTED'?[{field:'action_result',claim_value:'SUCCESS',proof_value:'FAIL',reason_code:'RESULT_MISMATCH'}]:[],missing_information:insufficient?[!p?'PROOF_MISSING':'PROOF_MAPPING_AMBIGUOUS']:[],reason_text:verdict==='SUPPORTED'?'가상 자료가 통화 성공 주장을 뒷받침합니다.':verdict==='CONTRADICTED'?'가상 통화 결과와 성공 주장이 충돌합니다.':'가상 증빙 또는 연결 근거가 부족합니다.',review_required:verdict!=='SUPPORTED',decision_policy_version:'mock-policy-v1.1',policy_hash:await hash('MOCK_POLICY'),proof_refs_hash:await hash(p?.proof_id||[]),verification_hash:await hash({claim:cl.claim_hash,proof:p?.proof_hash,verdict}),verification_tx_hash:null,chain_status:'MOCK',freshness_status:'CURRENT',review_status:'PENDING',created_at:stamp(),request_id:t.request_id};stale(c);c.verifications.push(v);s.requests[request]=v;return v;
 }
 const verifyPath=path.match(/^\/api\/v1\/verifications\/([^/]+)\/(reviews|integrity)$/);
 if(verifyPath){const c=s.cases.find(c=>c.verifications.some(v=>v.verification_id===verifyPath[1]));if(!c)bad('VERIFICATION_NOT_FOUND','검증 결과가 없습니다.',404);const v=c.verifications.find(v=>v.verification_id===verifyPath[1])!;
  if(verifyPath[2]==='integrity')return {is_simulated:true,verification_hash_matches:true,claim_hash_matches:true,onchain_matches:false,scope:'Mock 화면 시연입니다. 실제 온체인 무결성 검사를 실행하지 않습니다.'};
  if(!b)return {implemented:true,is_simulated:true,items:s.reviews.filter(r=>r.verification_id===v.verification_id)};
  allow('ADMIN');open(c);if(c.verifications.at(-1)!==v||v.freshness_status!=='CURRENT')bad('NEEDS_REVERIFICATION','최신 입력으로 재검증한 뒤 확인하세요.');if(b.verification_hash!==v.verification_hash)bad('VERIFICATION_HASH_MISMATCH','검증 참조가 다릅니다.',422);
  const status=String(b.review_status);if(!['ACKNOWLEDGED','ACCEPTED','REVISION_REQUESTED'].includes(status))bad('INVALID_REVIEW_STATUS','관리자 처리 상태를 확인하세요.',422);if(!String(b.reason_text||'').trim())bad('REASON_REQUIRED','확인·보완 사유를 입력하세요.',422);if(status==='ACCEPTED'&&v.verdict!=='SUPPORTED')bad('REVIEW_NOT_ACCEPTABLE','일치 판정만 단계 완료를 승인할 수 있습니다.');
  const r:Review={review_id:id('MOCK-REVIEW'),case_id:c.case_id,step_id:0,verification_id:v.verification_id,verification_hash:v.verification_hash,review_status:status,reviewer_id:'MOCK-ADMIN',reviewed_at:stamp(),reason_text:String(b.reason_text),review_hash:await hash({verification:v.verification_id,status,reason:b.reason_text}),review_tx_hash:null,chain_status:'MOCK',request_id:tx('ADMIN_REVIEW').request_id,is_simulated:true};s.reviews.push(r);v.review_status=status;return r;
 }
 bad('MOCK_ROUTE_NOT_FOUND','Mock에서 지원하지 않는 요청입니다.',404);
}
