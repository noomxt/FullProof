import {officialRequest} from './official';
import {signTypedProof} from './wallet';
import {mockRequest} from './mock';
export type Role='OFFICER'|'AGENCY'|'ADMIN';
export type ChainStatus='PENDING'|'SUBMITTED'|'CONFIRMED'|'FAILED'|'UNKNOWN'|'MOCK';
export interface Action {action_type:string;action_result:string;target_id:string|null;occurred_at:string|null;source_excerpt:string}
export interface Extraction {extraction_status:string;actions:Action[];model_name:string|null;prompt_version:string;review_required:boolean}
export interface Claim {claim_id:string;claim_version:number;case_id:string;step_id:number;claim_text:string;claim_created_at:string|null;claimed_occurred_at:string|null;claim_hash:string;claim_tx_hash:string|null;chain_status:ChainStatus;request_id:string;structured_claim:Extraction|null}
export interface Proof {proof_id:string;proof_version:number;case_id:string;step_id:number;call_id:string;issuer_agency_id:string;agency_address:string;action_type:string;target_id:string|null;result:string;proof_occurred_at:string;proof_issued_at:string;source_sha256:string;source_uri:string;source_bytes:string;proof_hash:string;proof_tx_hash:string|null;chain_status:ChainStatus;signature:string|null;mapping_reference:string;request_id?:string}
export interface Mapping {mapping_id:string;claim_id:string;claim_version:number;proof_id:string;proof_version:number;mapping_status:string;evidence_note:string;confirmed_at:string}
export type Verdict='SUPPORTED'|'CONTRADICTED'|'INSUFFICIENT';
export interface Verification {verification_id:string;case_id:string;step_id:number;claim_ref:{claim_id:string;claim_version:number;claim_hash:string};proof_refs:{proof_id:string;proof_version:number;proof_hash:string}[];processing_status:string;verdict:Verdict|null;conflicts:{field:string;claim_value:string|null;proof_value:string|null;reason_code:string}[];missing_information:string[];reason_text:string;review_required:boolean;decision_policy_version:string;policy_hash:string;proof_refs_hash:string;verification_hash:string;verification_tx_hash:string|null;chain_status:ChainStatus;freshness_status:string;review_status:string;created_at:string|null;request_id:string}
export interface Review {review_id:string;case_id:string;step_id:number;verification_id:string;verification_hash:string;review_status:string;reviewer_id:string;reviewed_at:string;reason_text:string;review_hash:string|null;review_tx_hash:string|null;chain_status:ChainStatus;request_id?:string;is_simulated?:boolean}
export type RequestState='PROCESSING'|'SUBMITTED'|'CONFIRMED'|'FAILED'|'UNKNOWN';
export interface VerificationRequest {verification_id:string;case_id:string;request_state:RequestState;phase:string;status_url:string;tx_hash:string|null;result:Verification|null;error:string|null}
export interface Case {verification_requests?:VerificationRequest[];steps?:{step_id:number;step_name:string;is_required:boolean}[];close_tx_hash?:string|null;region?:string;reviews?:Review[];is_simulated?:boolean;closed_at?:string;close_reason?:string;close_request_id?:string;case_id:string;title:string;status:string;created_at:string|null;scenario_id:string;claims:Claim[];proofs:Proof[];verifications:Verification[];mappings:Mapping[];close_eligible:boolean;close_blockers:string[]}
export interface System {policy_hash?:string;schema_version:string;environment:string;chain:{available:boolean;chain_id?:number;contract_address?:string;agency_address?:string;signer_address?:string;domain_version?:string;agency_nonce?:string;admin_address?:string;reviewer_addresses?:string[];rpc_url?:string};ai:{provider:string;is_simulated:boolean;key_configured:boolean};capabilities:{claim_anchor:boolean;proof_attestation:boolean;verification_anchor:boolean;admin_review:boolean;close_case:boolean};limitations:string[]}
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
export async function api<T>(path:string,body?:unknown):Promise<T>{
 if(isMockMode()){try{return await mockRequest<T>(path,body)}catch(e){const error=e as {code?:string;message?:string;status?:number};throw new ApiError(error.code||'MOCK_ERROR',error.message||'가상 처리 오류',error.status||503)}}
 try{return await officialRequest<T>(path,body)}catch(e){const error=e as {code?:string;message?:string;status?:number};throw new ApiError(error.code||'API_ERROR',error.code==='4001'||(error as {code?:unknown}).code===4001?'지갑 서명을 취소했습니다. 기록을 확인한 후 다시 시도할 수 있습니다.':error.message||'API 처리 오류',error.status||0)}

}
export async function setRole(role:Role){const s=await api<{token:string}>('/api/v1/demo/session',{role});localStorage.setItem('fullproof.demo.role',role);return role}
export async function signProof(draft:Draft):Promise<string>{if(isMockMode())return 'FRONTEND_MOCK_NO_SIGNATURE';return signTypedProof(draft)}
export const fmt=(value:string|null|undefined)=>value?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',dateStyle:'short',timeStyle:'medium'}).format(new Date(value)):'미확인';
export const short=(s:string|undefined|null)=>s?s.slice(0,12)+'…'+s.slice(-6):'—';
