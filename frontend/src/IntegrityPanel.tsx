import {OperationError} from './Details';
import {useState,useEffect} from 'react';
import {api,isMockMode} from './api';
import type {IntegrityReport} from './integrity';
import {Notice,Hash,Done} from './ui';
export default function IntegrityPanel({id}:{id:string}){
 const [report,setReport]=useState<IntegrityReport|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{setReport(null);setError('')},[id]);
 async function check(){setBusy(true);setError('');try{setReport(await api<IntegrityReport>('/api/v1/verifications/'+id+'/integrity'))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 if(isMockMode())return <Notice>온체인 대조는 API 연결이 필요합니다. 현재는 로컬 기록입니다.</Notice>;
 return <section className="integrity-panel"><h3>원문 해시 재계산·체인 대조</h3><p className="caption">Claim·기관 원문·Proof·판정·정책·참조 목록을 브라우저에서 다시 계산합니다.</p><button className="spaced" disabled={busy} onClick={()=>void check()}>{busy?'브라우저 계산·체인 대조 중…':'해시 재계산 및 온체인 대조'}</button>{error&&<OperationError message={error}/>}{report&&<><div className="spaced">{report.ok?<Done>계산·대조 완료 · 모든 항목 일치</Done>:<Notice error>일치하지 않거나 조회할 수 없는 항목이 있습니다. 아래 항목을 확인하세요.</Notice>}</div><p className="caption">체인 {report.chain_id} · 컨트랙트 {report.contract_address}</p><div className="integrity-checks">{report.checks.map((c,i)=><details key={i}><summary><span className={'badge '+(c.status==='MATCH'?'green':c.status==='MISMATCH'?'red':'amber')}>{c.status==='MATCH'?'일치':c.status==='MISMATCH'?'불일치':'조회 불가'}</span> {c.name}</summary><p>브라우저 재계산</p><Hash value={c.computed}/><p>저장·체인 기록</p><Hash value={c.recorded}/></details>)}</div><Notice>{report.scope}</Notice></>}</section>;
}
