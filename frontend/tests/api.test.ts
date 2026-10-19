import {beforeEach,afterEach,describe,it,expect,vi} from 'vitest';
import {api,setRole,signProof,setApiMode,type Draft} from '../src/api';
beforeEach(()=>setApiMode('api'));
afterEach(()=>{vi.unstubAllGlobals();delete window.ethereum});
describe('v1.1 API contract',()=>{
 it('unwraps successful responses and sends the demo role token',async()=>{
  const fetch=vi.fn().mockResolvedValueOnce({ok:true,status:200,json:async()=>({success:true,data:{token:'test-role-token'},error:null})}).mockResolvedValueOnce({ok:true,status:200,json:async()=>({success:true,data:[],error:null})});
  vi.stubGlobal('fetch',fetch);await setRole('OFFICER');expect(await api('/api/v1/cases')).toEqual([]);
  expect(fetch.mock.calls[1][1].headers.Authorization).toBe('Bearer test-role-token');
 });
 it('preserves the request ID after an ambiguous write failure',async()=>{
  const fetch=vi.fn().mockRejectedValue(new Error('connection lost'));vi.stubGlobal('fetch',fetch);
  await expect(api('/api/v1/proofs/anchor',{draft_id:'uncertain'})).rejects.toMatchObject({code:'CONNECTION_UNKNOWN'});
  await expect(api('/api/v1/proofs/anchor',{draft_id:'uncertain'})).rejects.toThrow();
  expect(fetch.mock.calls[0][1].headers['Idempotency-Key']).toBe(fetch.mock.calls[1][1].headers['Idempotency-Key']);
 });
 it('keeps NOT IMPLEMENTED responses distinct from a successful review',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:501,json:async()=>({success:false,data:null,error:{code:'ADMIN_REVIEW_NOT_IMPLEMENTED',message:'연결 대기'}})}));
  await expect(api('/api/v1/verifications/a/reviews',{})).rejects.toMatchObject({code:'ADMIN_REVIEW_NOT_IMPLEMENTED',status:501});
 });
 it('does not sign if the selected wallet is not the registered agency signer',async()=>{
  const request=vi.fn().mockResolvedValue(['0x111']);window.ethereum={request};
  await expect(signProof({signer_address:'0x222'} as Draft)).rejects.toThrow('기관 시연 계정');
  expect(request).toHaveBeenCalledTimes(1);
 });
 it('explains that MetaMask is missing without faking a signature',async()=>{
  await expect(signProof({} as Draft)).rejects.toThrow('MetaMask');
 });
});
