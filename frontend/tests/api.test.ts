import {beforeEach,afterEach,describe,it,expect,vi} from 'vitest';
import {api,setRole,signProof,setApiMode,type Draft} from '../src/api';
import {request} from '../src/official';
import {personal,walletAccount} from '../src/wallet';
const draft={signer_address:'0x222',typed_data:{domain:{chainId:31337}}} as Draft;
beforeEach(()=>setApiMode('api'));
afterEach(()=>{vi.unstubAllGlobals();delete window.ethereum});
describe('official API and wallet boundary',()=>{
 it('UI role selection never invents an authentication bearer token',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>([])});vi.stubGlobal('fetch',fetch);
  await setRole('OFFICER');expect(fetch).not.toHaveBeenCalled();expect(await api('/api/v1/cases')).toEqual([]);
  expect(fetch.mock.calls[0][0]).toBe('/backend/api/v1/frontend/cases');expect(fetch.mock.calls[0][1].headers.Authorization).toBeUndefined();
 });
 it('supports official wrapped and raw responses',async()=>{
  const fetch=vi.fn().mockResolvedValueOnce({ok:true,status:201,json:async()=>({case_id:'C1'})}).mockResolvedValueOnce({ok:true,status:200,json:async()=>({success:true,data:{verdict:'SUPPORTED'},error:null})});vi.stubGlobal('fetch',fetch);
  expect(await request('/raw')).toEqual({case_id:'C1'});expect(await request('/wrapped')).toEqual({verdict:'SUPPORTED'});
 });
 it('ambiguous POST does not retry or claim idempotency',async()=>{
  const fetch=vi.fn().mockRejectedValue(new Error('connection lost'));vi.stubGlobal('fetch',fetch);
  await expect(request('/api/v1/cases/C1/close',{signature:'x'})).rejects.toMatchObject({code:'CONNECTION_UNKNOWN'});
  expect(fetch).toHaveBeenCalledTimes(1);expect(fetch.mock.calls[0][1].headers['Idempotency-Key']).toBeUndefined();
 });
 it('official FastAPI error detail remains a failure',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:409,json:async()=>({detail:'Only SUPPORTED verification can be accepted'})}));
  await expect(request('/reviews',{})).rejects.toMatchObject({status:409,message:'Only SUPPORTED verification can be accepted'});
 });
 it('wrong institution account never signs',async()=>{
  const request=vi.fn().mockResolvedValue(['0x111']);window.ethereum={request};
  await expect(signProof(draft)).rejects.toThrow('등록된 서명 계정');expect(request).toHaveBeenCalledTimes(1);
 });
 it('missing MetaMask never produces a simulated signature in API mode',async()=>{await expect(signProof(draft)).rejects.toThrow('MetaMask')});
 it('a wallet rejection is not submitted as a signature',async()=>{
  window.ethereum={request:vi.fn(async({method})=>{if(method==='eth_accounts')return ['0x222'];if(method==='eth_chainId')return '0x7a69';throw Object.assign(Error('User rejected'),{code:4001})})};
  await expect(personal('한글 확인','0x222',31337)).rejects.toMatchObject({code:4001});
 });
 it('changing account during a signature invalidates the result',async()=>{
  let signed=false;window.ethereum={request:vi.fn(async({method})=>{if(method==='eth_accounts')return [signed?'0x333':'0x222'];if(method==='eth_chainId')return '0x7a69';if(method==='personal_sign'){signed=true;return '0xsigned'}return []})};
  await expect(personal('확인','0x222',31337)).rejects.toThrow('계정 또는 네트워크');
 });
});
