import {mockRequest} from './mock';
export type Role='OFFICER'|'AGENCY'|'ADMIN';
export type ChainStatus='PENDING'|'SUBMITTED'|'CONFIRMED'|'FAILED'|'UNKNOWN'|'MOCK';
export interface Action {action_type:string;action_result:string;target_id:string|null;occurred_at:string|null;source_excerpt:string}
export interface Extraction {extraction_status:string;actions:Action[];model_name:string;prompt_version:string;review_required:boolean}
export interface Claim {claim_id:string;claim_version:number;case_id:string;step_id:number;claim_text:string;claim_created_at:string;claimed_occurred_at:string|null;claim_hash:string;claim_tx_hash:string|null;chain_status:ChainStatus;request_id:string;structured_claim:Extraction|null}
export interface Proof {proof_id:string;proof_version:number;case_id:string;step_id:number;call_id:string;issuer_agency_id:string;agency_address:string;action_type:string;target_id:string|null;result:string;proof_occurred_at:string;proof_issued_at:string;source_sha256:string;source_uri:string;source_bytes:string;proof_hash:string;proof_tx_hash:string|null;chain_status:ChainStatus;signature:string|null;mapping_reference:string;request_id?:string}
export interface Mapping {mapping_id:string;claim_id:string;claim_version:number;proof_id:string;proof_version:number;mapping_status:string;evidence_note:string;confirmed_at:string}
export type Verdict='SUPPORTED'|'CONTRADICTED'|'INSUFFICIENT';
export interface Verification {verification_id:string;case_id:string;step_id:number;claim_ref:{claim_id:string;claim_version:number;claim_hash:string};proof_refs:{proof_id:string;proof_version:number;proof_hash:string}[];processing_status:string;verdict:Verdict;conflicts:{field:string;claim_value:string|null;proof_value:string|null;reason_code:string}[];missing_information:string[];reason_text:string;review_required:boolean;decision_policy_version:string;policy_hash:string;proof_refs_hash:string;verification_hash:string;verification_tx_hash:string|null;chain_status:ChainStatus;freshness_status:string;review_status:string;created_at:string;request_id:string}
export interface Review {review_id:string;case_id:string;step_id:number;verification_id:string;verification_hash:string;review_status:string;reviewer_id:string;reviewed_at:string;reason_text:string;review_hash:string|null;review_tx_hash:string|null;chain_status:ChainStatus;request_id?:string;is_simulated?:boolean}
export interface Case {region?:string;reviews?:Review[];is_simulated?:boolean;closed_at?:string;close_reason?:string;close_request_id?:string;case_id:string;title:string;status:string;created_at:string;scenario_id:string;claims:Claim[];proofs:Proof[];verifications:Verification[];mappings:Mapping[];close_eligible:boolean;close_blockers:string[]}
export interface System {schema_version:string;environment:string;chain:{available:boolean;chain_id?:number;contract_address?:string;agency_address?:string;signer_address?:string;domain_version?:string};ai:{provider:string;is_simulated:boolean;key_configured:boolean};capabilities:{claim_anchor:boolean;proof_attestation:boolean;verification_anchor:boolean;admin_review:boolean;close_case:boolean};limitations:string[]}
export interface TypedData {domain:{name:string;version:string;chainId:number;verifyingContract:string};types:Record<string,{name:string;type:string}[]>;primaryType:string;message:Record<string,string>}
export interface Draft {draft_id:string;proof:Proof;typed_data:TypedData;signer_address:string;domain_warning:string}
export interface Transaction {request_id:string;chain_status:ChainStatus;tx_hash:string|null;kind:string;error_code:string|null;is_simulated?:boolean}
export interface Scenario {id:string;title:string;note:string;claim_text:string;result:string|null}
export class ApiError extends Error {constructor(public code:string,message:string,public status:number){super(message)}}
export type ServiceMode='mock'|'api';
let mode:ServiceMode;try{mode=(localStorage.getItem('fullproof.service.mode')||import.meta.env.VITE_SERVICE_MODE||'mock') as ServiceMode}catch{mode='mock'}
export const isMockMode=()=>mode!=='api';
export function setApiMode(next:ServiceMode){mode=next;localStorage.setItem('fullproof.service.mode',next)}
export const isRecorded=(status:ChainStatus)=>status==='CONFIRMED'||status==='MOCK';
let token='';
const pendingKeys=new Map<string,string>();
const base=import.meta.env.VITE_API_BASE_URL||'http://127.0.0.1:8000';
export async function api<T>(path:string,body?:unknown):Promise<T>{
 if(isMockMode()){try{return await mockRequest<T>(path,body)}catch(e){const error=e as {code?:string;message?:string;status?:number};throw new ApiError(error.code||'MOCK_ERROR',error.message||'가상 처리 오류',error.status||503)}}
 const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),120000);
 const serialized=body===undefined?'':JSON.stringify(body);
 const signature=token+'|'+path+'|'+serialized;
 const write=body!==undefined&&!path.endsWith('/session');
 if(write&&!pendingKeys.has(signature))pendingKeys.set(signature,crypto.randomUUID());
 try{
  const res=await fetch(base+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{}) ,...(write?{'Idempotency-Key':pendingKeys.get(signature)!}:{})},body:body===undefined?undefined:serialized,signal:controller.signal});
  let out;try{out=await res.json()}catch{throw new ApiError('INVALID_RESPONSE','API 응답 형식을 확인해 주세요.',res.status)}
  if(res.status<500&&out.error?.code!=='REQUEST_STATUS_UNKNOWN')pendingKeys.delete(signature);
  if(!res.ok||!out.success)throw new ApiError(out.error?.code||'API_ERROR',out.error?.message||'요청을 처리하지 못했습니다.',res.status);
  return out.data as T;
 }catch(e){if(e instanceof ApiError)throw e;throw new ApiError('CONNECTION_UNKNOWN',body?'응답을 확인하지 못했습니다. 저장 요청을 다시 보내기 전에 새로고침과 거래 조회로 기존 결과를 확인하세요.':'백엔드에 연결할 수 없습니다. 실행 상태를 확인해 주세요.',0)}finally{clearTimeout(timeout)}
}
export async function setRole(role:Role){const s=await api<{token:string}>('/api/v1/demo/session',{role});token=s.token;localStorage.setItem('fullproof.demo.role',role);return role}
interface Provider {request(args:{method:string;params?:unknown[]}):Promise<unknown>}
declare global {interface Window {ethereum?:Provider}}
export async function signProof(draft:Draft):Promise<string>{
 if(isMockMode())return 'FRONTEND_MOCK_NO_SIGNATURE';
 const eth=window.ethereum;if(!eth)throw new Error('MetaMask 확장 프로그램을 설치한 브라우저에서 열어 주세요.');
 const accounts=await eth.request({method:'eth_requestAccounts'}) as string[];
 if(accounts[0]?.toLowerCase()!==draft.signer_address.toLowerCase())throw new Error(`기관 시연 계정 ${draft.signer_address}를 선택해 주세요.`);
 const wanted='0x'+draft.typed_data.domain.chainId.toString(16);
 if(await eth.request({method:'eth_chainId'})!==wanted){
  try{await eth.request({method:'wallet_switchEthereumChain',params:[{chainId:wanted}]})}
  catch(e){if((e as {code?:number}).code!==4902)throw e;await eth.request({method:'wallet_addEthereumChain',params:[{chainId:wanted,chainName:'FullProof Local Hardhat',rpcUrls:['http://127.0.0.1:8545'],nativeCurrency:{name:'Local test ETH',symbol:'ETH',decimals:18}}]});await eth.request({method:'wallet_switchEthereumChain',params:[{chainId:wanted}]})}
 }
 if(await eth.request({method:'eth_chainId'})!==wanted)throw new Error('Hardhat 네트워크를 확인해 주세요.');
 return await eth.request({method:'eth_signTypedData_v4',params:[accounts[0],JSON.stringify(draft.typed_data)]}) as string;
}
export const fmt=(value:string|null|undefined)=>value?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',dateStyle:'short',timeStyle:'medium'}).format(new Date(value)):'미확인';
export const short=(s:string|undefined|null)=>s?s.slice(0,12)+'…'+s.slice(-6):'—';
