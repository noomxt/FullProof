import {useEffect,useState} from 'react';
import type {Case,Role,System,Verification} from './api';
import {isMockMode} from './api';
import {Panel} from './ui';

export default function WorkflowCheck({item,role,system,verification,hasProof}:{
 item:Case; role:Role; system:System|null; verification:Verification|undefined; hasProof:boolean;
}){
 const [wallet,setWallet]=useState<{address:string;network:string}|null>(null);
 const [checking,setChecking]=useState(false);
 const [error,setError]=useState('');
 useEffect(()=>{setWallet(null);setError('')},[role,system]);
 async function check(){
  setWallet(null);setError('');setChecking(true);
  try{
   const provider=window.ethereum;
   if(!provider){setError('MetaMask를 사용할 수 없는 브라우저입니다.');return}
   const [accounts,network]=await Promise.all([provider.request({method:'eth_accounts'}),provider.request({method:'eth_chainId'})]);
   setWallet({address:(accounts as string[])[0]||'',network:String(network)});
  }catch{setError('지갑 상태를 조회하지 못했습니다.')}
  finally{setChecking(false)}
 }
 const chain=system?.chain;
 const addresses=role==='ADMIN'?[chain?.admin_address]:role==='AGENCY'?[chain?.signer_address]:chain?.reviewer_addresses||[];
 const expected=addresses.filter(Boolean);
 const account=wallet?.address;
 const roleStatus=expected.length===0?'등록 계정 확인 필요':!account?'확인 대기':expected.some(a=>a?.toLowerCase()===account.toLowerCase())?'등록 계정 일치':'등록 계정으로 전환 필요';
 const networkStatus=wallet&&chain?.chain_id?(Number(wallet.network)===chain.chain_id?'네트워크 일치':'네트워크 전환 필요'):'확인 대기';
 return <Panel title="시연 전 점검" side={!isMockMode()&&<button disabled={checking} onClick={()=>void check()}>{checking?'조회 중':'지갑 상태 확인'}</button>}>
  {error&&<p role="status">{error}</p>}
  <dl className="fields">
   <div><dt>지갑 연결</dt><dd>{isMockMode()?'가상 시연':wallet?(account?'연결됨':'사이트에 연결 필요'):'확인 대기'}</dd></div>
   <div><dt>역할 계정·네트워크</dt><dd>{isMockMode()?'가상 시연':roleStatus+' · '+networkStatus}</dd></div>
   <div><dt>기관 증빙</dt><dd>{hasProof?'기록 확인 완료':'확인된 증빙 없음'}</dd></div>
   <div><dt>최신 검증</dt><dd>{verification?.freshness_status==='CURRENT'?'최신 결과 있음':verification?'재검증 필요':'검증 대기'}</dd></div>
   <div><dt>선택한 수사 단계 승인</dt><dd>{verification?.review_status==='ACCEPTED'&&verification.freshness_status==='CURRENT'?'승인 완료':'승인 대기'}</dd></div>
   <div><dt>사건 종결</dt><dd>{item.status==='CLOSED'?'종결 완료':item.close_eligible?'종결 가능':'종결 조건 미충족'}</dd></div>
  </dl>
 </Panel>
}
