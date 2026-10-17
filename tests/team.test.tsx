// @vitest-environment jsdom
import React from 'react';
import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,cleanup} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {MemoryRouter} from 'react-router-dom';
import App from '../src/App';
import {teamRequest,signPayload} from '../src/api/team';
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const analysis={analysis_id:'A1',case_id:'C1',step_id:0,verdict:'INSUFFICIENT',processing_status:'NEEDS_REVIEW',reason_text:'증빙 검토 필요',is_provisional:true,structured_claim:{},action_results:[],execution:{provider:'fixture',is_simulated:true,label:'고정 응답 시연 · AI 호출 없음'}};
function backend(ready=true){
  const fetcher=vi.fn(async(url:unknown,init?:RequestInit)=>{
    const path=String(url);
    let data:unknown={};
    if(path.endsWith('/cases'))data=[{case_id:'C1',title:'가상 사건',is_closed:false,steps:[{step_id:0,step_name:'전화 확인'}]}];
    else if(path.endsWith('/system/status'))data={ai_ready:ready,environment:'LOCAL_DEMO',execution:analysis.execution,chain:{ready:true,chain_id:31337,block_number:1,contract_address:'0x123'},local_demo:null};
    else if(path.endsWith('/demo/scenarios'))data={scenarios:[]};
    else if(path.endsWith('/ai/drafts'))data={analysis};
    else if(path.endsWith('/history'))data={history:[analysis]};
    return {ok:true,json:async()=>data};
  });
  vi.stubGlobal('fetch',fetcher);return fetcher;
}
it('팀 API 초안과 고정 응답을 표시하고 근거 부족은 체인 저장을 막는다',async()=>{
  const fetcher=backend();const user=userEvent.setup();
  render(<MemoryRouter initialEntries={['/integration']}><App/></MemoryRouter>);
  await screen.findByRole('option',{name:'C1 · 가상 사건'});
  await user.selectOptions(screen.getByLabelText('팀 사건'),'C1');
  await user.click(screen.getByRole('button',{name:'기관 서명용 분석 초안 생성'}));
  await screen.findByText('서명 전 초안');
  expect((screen.getByRole('button',{name:'MetaMask 서명 및 저장 요청'}) as HTMLButtonElement).disabled).toBe(true);
  const call=fetcher.mock.calls.find(([url])=>String(url).endsWith('/ai/drafts'))!;
  const body=JSON.parse(call[1]!.body as string);
  expect(body.case_id).toBe('C1');expect(body.step_id).toBe(0);expect(body.proof.action_type).toBe('PHONE_CALL');
});
it('키가 없는 실제 모드는 분석 버튼을 비활성화한다',async()=>{
  backend(false);const user=userEvent.setup();
  render(<MemoryRouter initialEntries={['/integration']}><App/></MemoryRouter>);
  await screen.findByRole('option',{name:'C1 · 가상 사건'});
  await user.selectOptions(screen.getByLabelText('팀 사건'),'C1');
  expect((screen.getByRole('button',{name:'기관 서명용 분석 초안 생성'}) as HTMLButtonElement).disabled).toBe(true);
});
it('구조화된 백엔드 오류를 보존한다',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:503,json:async()=>({detail:{recovery_required:true,tx_hash:'0x123'}})})));
  await expect(teamRequest('/test')).rejects.toMatchObject({detail:{recovery_required:true}});
});
it('지갑이 없으면 서명 완료로 표시하지 않는다',async()=>{
  await expect(signPayload({domain:{chainId:31337},types:{},message:{}},'0x123')).rejects.toThrow('MetaMask');
});
it('기관 식별 주소와 별도의 등록 서명자를 지원한다',async()=>{
  const request=vi.fn(async({method}:{method:string})=>method==='eth_requestAccounts'?['0xsigner']:method==='eth_chainId'?'0x7a69':'0xsigned');
  vi.stubGlobal('ethereum',{request});
  await expect(signPayload({domain:{chainId:31337},types:{Proof:[]},message:{}},'0xagency','0xsigner')).resolves.toBe('0xsigned');
  expect(request).toHaveBeenCalledWith(expect.objectContaining({method:'eth_signTypedData_v4'}));
});
