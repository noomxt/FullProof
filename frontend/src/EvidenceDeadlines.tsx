import {createPortal} from 'react-dom';
import {useEffect,useState,type FormEvent} from 'react';
import {Link} from 'react-router-dom';
import {request} from './official';
import {isMockMode} from './api';
import {Notice,Panel} from './ui';

const endpoint='/api/v1/frontend/evidence-deadlines';
const statusLabels={NOT_SECURED:'미확보',REQUESTED:'요청 중',SECURED:'확보 완료'};
type Preservation=keyof typeof statusLabels;
type RecordItem={
 case_id:string; evidence_id:string; title:string; agency:string;
 evidence_expires_at:string|null; expected_at:string|null; deadline_source:string;
 preservation_status:Preservation; preservation_ref:string;
 days_until_expiry:number|null; deadline_status:string; warning_text:string;
 action_required:boolean; acquisition_overdue:boolean; acquisition_delay_days:number|null;
};
const initial={title:'',agency:'',expiry:'',expected:'',source:'',status:'NOT_SECURED' as Preservation,reference:''};
const toInput=(value:string|null)=>value?new Date(Date.parse(value)+9*3600000).toISOString().slice(0,16):'';
const toServer=(value:string)=>value?value+':00+09:00':null;
const dateLabel=(value:string)=>new Date(value).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'});

function State({row}:{row:RecordItem}){
 const days=row.days_until_expiry;
 const dday=row.deadline_status==='DEADLINE_PASSED'?(days===0?'D-Day · 기한 경과':'D+'+Math.abs(days??0)+' · 기한 경과'):
  days===null?'기한 확인 필요':days===0?'D-Day':'D-'+days;
 return <div>
  <p><strong>{statusLabels[row.preservation_status]}</strong> · {dday}{row.acquisition_overdue&&(' · '+(row.acquisition_delay_days?'확보 지연 '+row.acquisition_delay_days+'일':'확보 예정 시각 경과'))}</p>
  {row.action_required&&<p className="attention-text">{row.warning_text}</p>}
 </div>;
}

export default function EvidenceDeadlines({caseId,canEdit=false,emptyTarget}:{caseId?:string;canEdit?:boolean;emptyTarget?:HTMLElement|null}){
 const [rows,setRows]=useState<RecordItem[]>([]);
 const [form,setForm]=useState(initial);
 const [editing,setEditing]=useState<string|null>(null);
 const [busy,setBusy]=useState(false);
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState('');
 const [reload,setReload]=useState(0);
 const path=caseId?'/api/v1/frontend/cases/'+encodeURIComponent(caseId)+'/evidence-deadlines':endpoint;
 const mock=isMockMode();

 useEffect(()=>{
  if(mock)return;
  let active=true;
  const load=()=>{void request<RecordItem[]>(path).then(data=>{
   if(active){setRows(data);setError('');setLoading(false)}
  }).catch(e=>{if(active){setError(e.message);setLoading(false)}})};
  setLoading(true);setRows([]);load();
  return ()=>{active=false};
 },[path,mock,reload]);

 function edit(row:RecordItem){
  setEditing(row.evidence_id);
  setForm({title:row.title,agency:row.agency,expiry:toInput(row.evidence_expires_at),
   expected:toInput(row.expected_at),source:row.deadline_source,status:row.preservation_status,reference:row.preservation_ref});
 }

 async function save(event:FormEvent){
  event.preventDefault();
  if(busy||!canEdit)return;
  setBusy(true);setError('');
  try{
   const saved=await request<RecordItem>(path,{evidence_id:editing,title:form.title,agency:form.agency,
    evidence_expires_at:toServer(form.expiry),expected_at:toServer(form.expected),
    deadline_source:form.source,preservation_status:form.status,preservation_ref:form.reference});
   setRows(old=>[saved,...old.filter(row=>row.evidence_id!==saved.evidence_id)]);
   setEditing(null);setForm(initial);
  }catch(e){setError(e instanceof Error?e.message:'저장에 실패했습니다.')}
  finally{setBusy(false)}
 }

 if(mock)return null;
 const panel = <Panel title={caseId?'증거 확보·보존기한':'증거 확보·보존기한 경고'} side={<button disabled={loading||busy} onClick={()=>setReload(n=>n+1)}>상태 새로고침</button>}>
  {error&&<Notice error>{error}</Notice>}
  {loading?<p>기록을 조회하는 중입니다.</p>:!error&&rows.length===0&&<p>{caseId?'등록된 증거 확보 기록이 없습니다.':'확인이 필요한 증거가 없습니다.'}</p>}
  {rows.map(row=><article key={row.evidence_id} className="review-row">
   <strong>{row.title} · {row.agency}</strong><State row={row}/>
   {caseId?<p className="caption">보존기한 {row.evidence_expires_at?dateLabel(row.evidence_expires_at):'미확인'} · 확보 예정 {row.expected_at?dateLabel(row.expected_at):'미설정'}</p>:<Link className="text-link" to={'/cases/'+encodeURIComponent(row.case_id)+'?tab=overview'}>사건 보기</Link>}
   {caseId&&row.deadline_source&&<p className="caption">기한 출처 {row.deadline_source}</p>}
   {caseId&&row.preservation_status==='SECURED'&&<p className="caption">확보 근거 {row.preservation_ref}</p>}
   {canEdit&&<button disabled={busy} onClick={()=>edit(row)}>기록 수정</button>}
  </article>)}
  {canEdit&&!loading&&<form onSubmit={save} className="spaced">
   <h3>{editing?'확보 기록 수정':'확보 기록 등록'}</h3>
   <fieldset disabled={busy}>
    <label>증거명<input className="team-input" required maxLength={120} value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label>
    <label>요청 기관<input className="team-input" required maxLength={120} value={form.agency} onChange={e=>setForm({...form,agency:e.target.value})}/></label>
    <label>확보 예정일시 (한국시간)<input className="team-input" type="datetime-local" value={form.expected} onChange={e=>setForm({...form,expected:e.target.value})}/></label>
    <label>보존 만료일시 (한국시간)<input className="team-input" type="datetime-local" value={form.expiry} onChange={e=>setForm({...form,expiry:e.target.value})}/></label>
    <label>보존기한 확인 출처<input className="team-input" required={!!form.expiry} maxLength={500} value={form.source} onChange={e=>setForm({...form,source:e.target.value})}/></label>
    <label>확보 상태<select className="team-input" value={form.status} onChange={e=>setForm({...form,status:e.target.value as Preservation})}>{Object.entries(statusLabels).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
    {form.status==='SECURED'&&<label>확보 확인 근거<input className="team-input" required maxLength={500} value={form.reference} onChange={e=>setForm({...form,reference:e.target.value})}/></label>}
    <div className="actions"><button type="submit" className="primary">저장</button>{editing&&<button type="button" onClick={()=>{setEditing(null);setForm(initial)}}>수정 취소</button>}</div>
   </fieldset>
  </form>}
 </Panel>;
 return emptyTarget&&!loading&&!error&&rows.length===0 ? createPortal(panel,emptyTarget) : panel;
}
