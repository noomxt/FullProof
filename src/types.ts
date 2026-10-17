export type Stage = '요청' | '제공' | '열람';
export type Verdict = '일치' | '불일치' | '추가 확인' | '검증 보류';
export type ChainStatus = '미연결' | '저장 대기' | '저장 실패';
export interface Case { id:string; title:string; region:string; status:'진행 중'|'종결'; openedAt:string; summary:string }
export interface Evidence { id:string; agency:string; source:string; stage:Stage; location:string; time:string; caseId:string }
export interface Claim { id:string; caseId:string; text:string; type:string; stage:Stage; location:string; time:string; target:string; result:string; proof:Evidence|null }
export interface Comparison { field:string; claim:string; proof:string; status:'일치'|'불일치'|'확인 불가' }
export interface Verification { id:string; claimId:string; caseId:string; createdAt:string; verdict:Verdict; comparisons:Comparison[]; rationale:string; nextAction:string; demo:true; chain:{status:ChainStatus; transactionHash:null; recordHash:string|null} }
export interface FullProofApi { cases():Promise<Case[]>; claims(caseId:string):Promise<Claim[]>; claim(id:string):Promise<Claim|null>; verify(id:string,fail?:boolean):Promise<Verification>; history():Promise<Verification[]>; queue(id:string,fail?:boolean):Promise<Verification>; reset():Promise<void> }
