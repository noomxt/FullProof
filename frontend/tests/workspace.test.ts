import {createElement as h} from 'react';
import {MemoryRouter} from 'react-router-dom';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {webcrypto} from 'node:crypto';
import App from '../src/App';
import AdminReview from '../src/AdminReview';
import {isConfirmedApproval} from '../src/ApprovalReceipt';
import {api,setRole} from '../src/api';
import type {Case,Claim,Draft,Review,System,Verification} from '../src/api';
import {resetMock,setMockLatency,setMockFailure,scenarios} from '../src/mock';

// Browser-only fixtures are injected at the module boundary, never selected in the product.
vi.mock('../src/api',async importOriginal=>{
 const original=await importOriginal<typeof import('../src/api')>();
 const fixture=await import('../src/mock');
 return {...original,isMockMode:()=>true,api:fixture.mockRequest,setRole:async(role:string)=>{await fixture.mockRequest('/api/v1/demo/session',{role});localStorage.setItem('fullproof.demo.role',role);return role}};
});

beforeEach(()=>{
 localStorage.clear();resetMock();setMockLatency(0);
 vi.stubGlobal('crypto',webcrypto);vi.stubGlobal('isSecureContext',true);
 vi.stubGlobal('matchMedia',()=>({matches:true,addEventListener:()=>{},removeEventListener:()=>{}}));
 vi.stubGlobal('scrollTo',()=>{});HTMLElement.prototype.scrollIntoView=()=>{};
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals()});

it('starts on the role home even when the last role was administrator',async()=>{
 localStorage.setItem('fullproof.demo.role','ADMIN');
 render(h(MemoryRouter,null,h(App)));
 expect(screen.getByRole('heading',{name:'업무 시스템 접속'})).toBeTruthy();
 expect(screen.getByRole('button',{name:'수사담당자로 시작'})).toBeTruthy();
 expect(screen.queryByRole('heading',{name:'관리자 검토 대시보드'})).toBeNull();
 await act(async()=>{});
});

it('enters each role and returns home without deleting case data',async()=>{
 render(h(MemoryRouter,null,h(App)));
 for(const [button,title] of [['수사담당자로 시작','수사담당자 업무 대시보드'],['원천기관으로 시작','원천기관 증빙 데스크'],['관리자로 시작','관리자 검토 대시보드']]){
  fireEvent.click(screen.getByRole('button',{name:button}));
  await screen.findByRole('heading',{name:title});
  expect(screen.getByText('API 연결됨')).toBeTruthy();
  expect(screen.queryByText('연결 설정',{exact:true})).toBeNull();
  expect(screen.queryByLabelText('실행 모드')).toBeNull();
  expect(screen.getByText('환경 안내 · 예제 데이터')).toBeTruthy();
  expect(screen.queryByText('DEMO',{exact:true})).toBeNull();
  await screen.findByRole('link',{name:'실종 사건 · 안산 중앙',exact:true});
  fireEvent.click(screen.getByRole('link',{name:'홈',exact:true}));
  await screen.findByRole('heading',{name:'업무 시스템 접속'});
 }
 expect(await api<Case[]>('/api/v1/cases')).toHaveLength(4);
});

async function prepared(){
 await setRole('OFFICER');const c=await api<Case>('/api/v1/cases',{title:'승인 효과 테스트',scenario_id:'supported'});
 const cl=await api<Claim>('/api/v1/cases/'+c.case_id+'/claims',{claim_text:scenarios[0].claim_text,step_id:0});
 await api('/api/v1/claims/'+cl.claim_id+'/extract',{});
 await setRole('AGENCY');const d=await api<Draft>('/api/v1/proofs/drafts',{case_id:c.case_id,step_id:0});
 await api('/api/v1/proofs/anchor',{draft_id:d.draft_id,signature:'MOCK'});
 await setRole('OFFICER');await api('/api/v1/claims/'+cl.claim_id+'/proof-mappings',{claim_version:1,proof_id:d.proof.proof_id,proof_version:1});
 await api<Verification>('/api/v1/verifications',{claim_id:cl.claim_id,claim_version:1,request_id:crypto.randomUUID()});
 await setRole('ADMIN');return await api<Case>('/api/v1/cases/'+c.case_id);
}
const system={capabilities:{admin_review:true,close_case:true}} as System;
it('stamps once after saved approval and blocks repeated clicks while saving',async()=>{
 const item=await prepared();setMockLatency(25);
 render(h(AdminReview,{item,system,role:'ADMIN',onChange:async()=>{}}));
 await screen.findByText('아직 관리자 확인 이력이 없습니다.');
 fireEvent.change(screen.getByLabelText('관리자 처리'),{target:{value:'ACCEPTED'}});
 fireEvent.change(screen.getByLabelText('관리자 사유'),{target:{value:'최신 증빙과 근거를 확인했습니다.'}});
 const button=screen.getByRole('button',{name:'관리자 확인 기록'});
 fireEvent.click(button);fireEvent.click(button);
 expect((button as HTMLButtonElement).disabled).toBe(true);
 expect(screen.queryByLabelText('가상 승인 기록 완료')).toBeNull();
 await screen.findByLabelText('가상 승인 기록 완료');
 const saved=await api<Case>('/api/v1/cases/'+item.case_id);expect(saved.reviews).toHaveLength(1);
});
it('shows an error and never stamps when saving fails',async()=>{
 const item=await prepared();render(h(AdminReview,{item,system,role:'ADMIN',onChange:async()=>{}}));
 await screen.findByText('아직 관리자 확인 이력이 없습니다.');
 fireEvent.change(screen.getByLabelText('관리자 처리'),{target:{value:'ACCEPTED'}});
 fireEvent.change(screen.getByLabelText('관리자 사유'),{target:{value:'확인 완료'}});
 setMockFailure('error');fireEvent.click(screen.getByRole('button',{name:'관리자 확인 기록'}));
 await screen.findByRole('alert');await waitFor(()=>expect(screen.queryByLabelText('가상 승인 기록 완료')).toBeNull());
});
it('never stamps acknowledgement, pending records, cancelled signatures or another verification',()=>{
 const r={verification_id:'V1',review_status:'ACCEPTED',chain_status:'CONFIRMED',review_tx_hash:'0x123'} as Review;
 expect(isConfirmedApproval(r,'V1',false)).toBe(true);
 expect(isConfirmedApproval(undefined,'V1',false)).toBe(false);
 for(const patch of [{review_status:'ACKNOWLEDGED'},{chain_status:'SUBMITTED'},{review_tx_hash:null},{verification_id:'V2'}])expect(isConfirmedApproval({...r,...patch},'V1',false)).toBe(false);
 expect(isConfirmedApproval({...r,chain_status:'MOCK',review_tx_hash:null},'V1',true)).toBe(true);
 expect(isConfirmedApproval({...r,chain_status:'MOCK'},'V1',false)).toBe(false);
});

it('opens administrator evidence first and shows the review form only after navigation',async()=>{
 const item=await prepared();
 render(h(MemoryRouter,{initialEntries:['/cases/'+item.case_id+'?tab=verification']},h(App)));
 await screen.findByRole('heading',{name:'검토할 검증 결과'});
 expect(screen.getByRole('heading',{name:'수사 기록 ↔ 기관 증빙 비교'})).toBeTruthy();
 expect(screen.queryByRole('button',{name:'관리자 확인 기록'})).toBeNull();
 const technical=document.querySelector('details.technical-details') as HTMLDetailsElement;
 expect(technical).toBeTruthy();expect(technical.open).toBe(false);
 fireEvent.click(screen.getByRole('button',{name:'관리자 확인으로 이동'}));
 await screen.findByRole('button',{name:'관리자 확인 기록'});
});
