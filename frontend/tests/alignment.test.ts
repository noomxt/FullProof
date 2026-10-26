import {beforeEach,afterEach,it,expect,vi} from 'vitest';
import {api,setApiMode} from '../src/api';
const policy='0x'+'a'.repeat(64);
const config={schema_version:'1.1',environment:'LOCAL',policy_hash:policy,chain:{available:true},ai:{is_simulated:true},capabilities:{}};
const claim={claim_id:'CL-ALIGN',claim_version:1,case_id:'CASE-ALIGN',step_id:0,claim_text:'가상 통화 기록'};
const baseCase={case_id:'CASE-ALIGN',claims:[claim],proofs:[],mappings:[],verifications:[] as object[]};
const result={verification_id:'V-ALIGN',case_id:'CASE-ALIGN',processing_status:'COMPLETED',verdict:'INSUFFICIENT',claim_ref:{claim_id:'CL-ALIGN',claim_version:1,claim_hash:'0x'+'b'.repeat(64)},proof_refs:[],policy_hash:policy,chain_status:'CONFIRMED',verification_tx_hash:'0x'+'c'.repeat(64)};
const response=(data:unknown,status=200)=>({ok:status<400,status,json:async()=>data});
beforeEach(()=>{localStorage.clear();setApiMode('api')});afterEach(()=>vi.unstubAllGlobals());
it('prefers the team system/status route when its agreed UI fields exist',async()=>{const fetch=vi.fn().mockResolvedValue(response({success:true,data:config,error:null}));vi.stubGlobal('fetch',fetch);expect(await api('/api/v1/system/status')).toEqual(config);expect(fetch.mock.calls[0][0]).toBe('/backend/api/v1/system/status');expect(fetch).toHaveBeenCalledTimes(1)});
it('uses read-only status fallback only after official 404',async()=>{const fetch=vi.fn().mockResolvedValueOnce(response({detail:'Not Found'},404)).mockResolvedValueOnce(response(config));vi.stubGlobal('fetch',fetch);expect(await api('/api/v1/system/status')).toEqual(config);expect(fetch.mock.calls[1][0]).toBe('/backend/api/v1/frontend/status')});
it('does not hide an incompatible official status schema',async()=>{const fetch=vi.fn().mockResolvedValue(response({status:'healthy'}));vi.stubGlobal('fetch',fetch);await expect(api('/api/v1/system/status')).rejects.toThrow('응답 구조');expect(fetch).toHaveBeenCalledTimes(1)});
it('posts official claim/proofs payload without the removed parallel job API',async()=>{
 const fetch=vi.fn(async(url:string,options:{method:string;body?:string})=>{if(url.endsWith('/frontend/cases'))return response([baseCase]);if(url.endsWith('/system/status'))return response(config);return response({success:true,data:result,error:null},201)});vi.stubGlobal('fetch',fetch);
 expect(await api('/api/v1/verifications',{claim_id:claim.claim_id,claim_version:1})).toEqual(result);
 const post=fetch.mock.calls.find(c=>c[1].method==='POST')!;expect(post[0]).toBe('/backend/api/v1/verifications');expect(JSON.parse(post[1].body!)).toEqual({claim:{case_id:claim.case_id,claim_id:claim.claim_id,claim_version:1},proofs:[]});expect(fetch.mock.calls.some(c=>c[0].includes('verification-requests'))).toBe(false);
});
it('blocks a second verification POST after an ambiguous response',async()=>{
 const fetch=vi.fn(async(url:string)=>{if(url.endsWith('/frontend/cases'))return response([baseCase]);if(url.endsWith('/system/status'))return response(config);throw Error('Lost response')});vi.stubGlobal('fetch',fetch);
 await expect(api('/api/v1/verifications',{claim_id:claim.claim_id,claim_version:1})).rejects.toMatchObject({code:'CONNECTION_UNKNOWN'});
 await expect(api('/api/v1/verifications',{claim_id:claim.claim_id,claim_version:1})).rejects.toThrow('자동 재전송을 막았습니다');expect(fetch.mock.calls.filter(c=>c[0].endsWith('/api/v1/verifications'))).toHaveLength(1);
});
it('recovers only a newly stored matching result instead of sending another POST',async()=>{
 localStorage.setItem('fullproof.uncertain.verification.CASE-ALIGN:CL-ALIGN:1',JSON.stringify({previous_ids:[],proof_refs:[],policy_hash:policy}));
 const fetch=vi.fn(async(url:string)=>url.endsWith('/frontend/cases')?response([{...baseCase,verifications:[result]}]):response(config));vi.stubGlobal('fetch',fetch);
 expect(await api('/api/v1/verifications',{claim_id:claim.claim_id,claim_version:1})).toEqual(result);expect(fetch.mock.calls.some(c=>c[0].endsWith('/api/v1/verifications'))).toBe(false);
});
