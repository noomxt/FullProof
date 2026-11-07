import {beforeEach,describe,it,expect,vi} from 'vitest';
import {webcrypto} from 'node:crypto';
import {mockRequest as request,resetMock,setMockLatency,setMockFailure,scenarios} from '../src/mock';
import type {Case,Claim,Draft,Review,Verification} from '../src/api';
let scenario='supported';
async function role(role:string){await request('/api/v1/demo/session',{role})}
async function flow(type=scenario){
 await role('OFFICER');const c=await request<Case>('/api/v1/cases',{title:'가상 사건',scenario_id:type});
 const cl=await request<Claim>(`/api/v1/cases/${c.case_id}/claims`,{claim_text:scenarios[0].claim_text,step_id:0});
 await request(`/api/v1/claims/${cl.claim_id}/extract`,{});
 if(type!=='insufficient'){
  await role('AGENCY');const d=await request<Draft>('/api/v1/proofs/drafts',{case_id:c.case_id,step_id:0});
  await request('/api/v1/proofs/anchor',{draft_id:d.draft_id,signature:'MOCK'});
  await role('OFFICER');await request(`/api/v1/claims/${cl.claim_id}/proof-mappings`,{claim_version:1,proof_id:d.proof.proof_id,proof_version:1});
 }
 await role('OFFICER');const v=await request<Verification>('/api/v1/verifications',{claim_id:cl.claim_id,claim_version:1,request_id:webcrypto.randomUUID()});
 return {c,cl,v};
}
async function review(v:Verification,status='ACCEPTED',reason='확인했습니다.'){
 return request<Review>(`/api/v1/verifications/${v.verification_id}/reviews`,{verification_hash:v.verification_hash,review_status:status,reason_text:reason});
}
beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);localStorage.clear();resetMock();setMockLatency(0);scenario='supported'});
describe('v1.1 frontend Mock lifecycle',()=>{
 it('loads four synthetic cases without a backend',async()=>{expect(await request<Case[]>('/api/v1/cases')).toHaveLength(4)});
 it('records no transaction hash or actual CONFIRMED status',async()=>{const {cl,v}=await flow();expect(cl.claim_tx_hash).toBeNull();expect(v.verification_tx_hash).toBeNull();expect(v.chain_status).toBe('MOCK')});
 it('blocks closure before admin acceptance and allows it afterwards',async()=>{
  const {c,v}=await flow();await role('ADMIN');await expect(request(`/api/v1/cases/${c.case_id}/close`,{reason_text:'종결'})).rejects.toMatchObject({code:'CLOSE_BLOCKED'});
  await review(v);const next=await request<Case>(`/api/v1/cases/${c.case_id}`);expect(next.close_eligible).toBe(true);
  const closed=await request<Case>(`/api/v1/cases/${c.case_id}/close`,{reason_text:'검증·승인 완료'});expect(closed.status).toBe('CLOSED');expect(closed.close_reason).toBe('검증·승인 완료');
  await role('OFFICER');await expect(request(`/api/v1/cases/${c.case_id}/claims`,{claim_text:'수정'})).rejects.toMatchObject({code:'CASE_ALREADY_CLOSED'});
 });
 it('does not treat acknowledgement as approval',async()=>{const {c,v}=await flow();await role('ADMIN');await review(v,'ACKNOWLEDGED');expect((await request<Case>(`/api/v1/cases/${c.case_id}`)).close_blockers).toContain('ADMIN_REVIEW_NOT_ACCEPTED')});
 it.each(['contradicted','insufficient','ambiguous'])('blocks acceptance and closure for %s',async(type)=>{const {c,v}=await flow(type);await role('ADMIN');await expect(review(v)).rejects.toMatchObject({code:'REVIEW_NOT_ACCEPTABLE'});await review(v,'REVISION_REQUESTED');const r=await request<Case>(`/api/v1/cases/${c.case_id}`);expect(r.close_eligible).toBe(false);expect(r.reviews?.at(-1)?.review_status).toBe('REVISION_REQUESTED')});
 it('preserves an old acceptance but requires review after Claim revision',async()=>{
  const {c,cl,v}=await flow();await role('ADMIN');await review(v);await role('OFFICER');const cl2=await request<Claim>(`/api/v1/cases/${c.case_id}/claims`,{claim_text:cl.claim_text,claim_id:cl.claim_id});expect(cl2.claim_version).toBe(2);
  const updated=await request<Case>(`/api/v1/cases/${c.case_id}`);expect(updated.verifications[0].freshness_status).toBe('NEEDS_REVERIFICATION');expect(updated.reviews).toHaveLength(1);expect(updated.close_eligible).toBe(false);
  await request(`/api/v1/claims/${cl.claim_id}/extract`,{});const next=await request<Verification>('/api/v1/verifications',{claim_id:cl.claim_id,claim_version:2,request_id:crypto.randomUUID()});expect(next.review_status).toBe('PENDING');await role('ADMIN');await expect(review(v)).rejects.toMatchObject({code:'NEEDS_REVERIFICATION'});
 });
 it('enforces reviewer role and a nonempty reason',async()=>{const {v}=await flow();await expect(review(v)).rejects.toMatchObject({code:'ROLE_NOT_ALLOWED'});await role('ADMIN');await expect(review(v,'ACCEPTED',' ')).rejects.toMatchObject({code:'REASON_REQUIRED'})});
 it('does not mutate the original verdict when reviewed',async()=>{const {c,v}=await flow('contradicted');await role('ADMIN');await review(v,'REVISION_REQUESTED');expect((await request<Case>(`/api/v1/cases/${c.case_id}`)).verifications[0].verdict).toBe('CONTRADICTED')});
 it('supports failure then successful retry without creating a failed result',async()=>{await role('OFFICER');setMockFailure('error');await expect(request('/api/v1/cases',{title:'사건',scenario_id:'supported'})).rejects.toMatchObject({code:'MOCK_REQUEST_FAILED'});expect(await request<Case[]>('/api/v1/cases')).toHaveLength(4);await request('/api/v1/cases',{title:'사건',scenario_id:'supported'});expect(await request<Case[]>('/api/v1/cases')).toHaveLength(5)});
 it('rejects arbitrary natural language in a fixed fixture',async()=>{await role('OFFICER');const c=(await request<Case[]>('/api/v1/cases'))[0];const cl=await request<Claim>(`/api/v1/cases/${c.case_id}/claims`,{claim_text:'임의 텍스트'});await expect(request(`/api/v1/claims/${cl.claim_id}/extract`,{})).rejects.toMatchObject({code:'MOCK_FIXTURE_ONLY'})});
});
