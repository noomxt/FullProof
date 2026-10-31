import {TechnicalDetails,OperationError} from './Details';
import {useEffect,useRef,useState} from 'react';
import {LoaderCircle} from 'lucide-react';
import ApprovalReceipt,{isConfirmedApproval} from './ApprovalReceipt';
import {api,fmt,isMockMode} from './api';
import type {Case,Review,Role,System} from './api';
import {Badge,Empty,Hash,Notice,Panel,Done,label} from './ui';

export const blockerLabel=(code:string)=>({CASE_ALREADY_CLOSED:'이미 종결된 사건입니다.',CLAIM_NOT_ANCHORED:'최신 Claim 원문 기록이 필요합니다.',VERIFICATION_PENDING:'검증 실행이 필요합니다.',NEEDS_REVERIFICATION:'입력이 변경되어 재검증이 필요합니다.',VERIFICATION_CONTRADICTED:'불일치 항목을 보완해야 합니다.',VERIFICATION_INSUFFICIENT:'검증할 증빙·연결 근거가 부족합니다.',PROOF_MISSING:'연결된 기관 Proof가 없습니다.',ADMIN_REVIEW_PENDING:'최신 검증에 대한 관리자 확인이 필요합니다.',ADMIN_REVIEW_NOT_ACCEPTED:'최신 검증에 대한 단계 완료 승인이 필요합니다.',ADMIN_REVIEW_NOT_IMPLEMENTED:'관리자 이력 API 연결 대기',V11_CLOSE_CONTRACT_NOT_IMPLEMENTED:'v1.1 종결 컨트랙트 연결 대기'} as Record<string,string>)[code]||code;

export default function AdminReview({item,system,role,onChange}:{item:Case;system:System|null;role:Role;onChange:()=>Promise<void>}){
 const v=item.verifications.at(-1),mock=isMockMode();
 const inFlight=useRef(false);const [approval,setApproval]=useState<Review|null>(null);const [operation,setOperation]=useState('');
 const [status,setStatus]=useState('ACKNOWLEDGED'),[reason,setReason]=useState(''),[closeReason,setCloseReason]=useState(''),[rows,setRows]=useState<Review[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 async function load(){if(!v){setRows([]);return []}const result=await api<{items:Review[]}>('/api/v1/verifications/'+v.verification_id+'/reviews');setRows(result.items);return result.items}
 useEffect(()=>{void load().catch(e=>setError(e.message));setMessage('');setApproval(null);setStatus('ACKNOWLEDGED')},[v?.verification_id]);
 const editable=role==='ADMIN'&&item.status==='OPEN'&&v?.freshness_status==='CURRENT'&&(mock||v.chain_status==='CONFIRMED');
 const acceptable=v?.verdict==='SUPPORTED'&&v.freshness_status==='CURRENT'&&(mock||v.chain_status==='CONFIRMED');
 async function saveReview(){
  if(inFlight.current||!v)return;
  inFlight.current=true;setBusy(true);setOperation('관리자 확인');setApproval(null);
  document.documentElement.dataset.fullproofBusy='true';window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:true}));setError('');setMessage('');
  const previousIds=new Set(rows.map(r=>r.review_id));
  try{
   await api('/api/v1/verifications/'+v.verification_id+'/reviews',{review_status:status,reason_text:reason,verification_hash:v.verification_hash});
   await onChange();const saved=await load();
   const confirmed=saved.find(r=>!previousIds.has(r.review_id)&&r.reason_text===reason&&r.verification_hash===v.verification_hash&&isConfirmedApproval(r,v.verification_id,mock));
   if(status==='ACCEPTED'&&confirmed)setApproval(confirmed);
   setReason('');setMessage(mock?'관리자 확인을 저장했습니다. · 로컬, 온체인 미저장':'관리자 확인 요청을 처리했습니다. 기록 상태를 확인하세요.');
  }catch(e){setError(e instanceof Error?e.message:'처리 실패')}
  finally{inFlight.current=false;setBusy(false);setOperation('');delete document.documentElement.dataset.fullproofBusy;window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:false}))}
 }
 async function close(){
  if(inFlight.current)return;
  inFlight.current=true;setBusy(true);setOperation('사건 종결');setApproval(null);
  document.documentElement.dataset.fullproofBusy='true';window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:true}));setError('');setMessage('');
  try{await api('/api/v1/cases/'+item.case_id+'/close',{reason_text:closeReason});await onChange();setMessage(mock?'사건 상태를 종결로 변경했습니다. · 로컬 저장':'종결 요청을 처리했습니다. 서버 결과를 확인하세요.')}
  catch(e){setError(e instanceof Error?e.message:'종결 실패')}
  finally{inFlight.current=false;setBusy(false);setOperation('');delete document.documentElement.dataset.fullproofBusy;window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:false}))}
 }

 return <Panel title="06 · 관리자 확인·종결" side={item.status==='CLOSED'?<Badge value="CLOSED"/>:undefined}>
 <Notice>{mock?'로컬 검토 기록 · 전자서명·온체인 저장 없음':'관리자 지갑의 메시지 서명 후 백엔드가 승인·종결 거래를 제출합니다. 서명을 취소하면 요청을 제출하지 않습니다.'}</Notice>
 {busy&&<div className="working" role="status"><LoaderCircle className="spin" size={18}/>{operation} 처리 중입니다. 지갑 서명과 서버 기록을 기다려 주세요.</div>}{approval&&<ApprovalReceipt key={approval.review_id} review={approval} mock={mock}/>}
 {error&&<OperationError message={error}/>}{message&&<Done>{message}</Done>}
 {role!=='ADMIN'&&<p className="caption">업무 역할을 ‘관리자’로 변경해 확인·보완·승인을 진행하세요.</p>}
 {v&&<TechnicalDetails title="검토 대상 기록 상세"><p className="caption">대상 검증: {v.verification_id}<br/>Claim v{v.claim_ref.claim_version} · <Badge value={v.freshness_status}/></p></TechnicalDetails>}
 <label>관리자 처리<select className="full-width spaced" aria-label="관리자 처리" value={status} onChange={e=>setStatus(e.target.value)} disabled={busy||!editable}><option value="ACKNOWLEDGED">결과 확인</option><option value="REVISION_REQUESTED">보완 요청</option><option value="ACCEPTED" disabled={!acceptable}>단계 완료 승인</option></select></label>
 <label>확인·보완 사유<textarea aria-label="관리자 사유" className="team-input" value={reason} onChange={e=>setReason(e.target.value)} rows={2} maxLength={1000} disabled={busy||!editable}/></label>
 <button className="primary" disabled={busy||!editable||!system?.capabilities.admin_review||!reason.trim()||(status==='ACCEPTED'&&!acceptable)} onClick={()=>void saveReview()}>{busy?<><LoaderCircle className="spin" size={16}/>처리 중…</>:system?.capabilities.admin_review?'관리자 확인 기록':'관리자 확인 기록 · 연결 대기'}</button>
 <p className="caption">결과 확인은 완료 승인이 아닙니다. 불일치·근거 부족·재검증 필요 상태는 단계 완료를 승인할 수 없습니다.</p>
 <div className="review-history"><h3>최신 검증의 관리자 확인 이력</h3>{!rows.length?<Empty>아직 관리자 확인 이력이 없습니다.</Empty>:rows.map(r=><article className="review-row" key={r.review_id}><div><Badge value={r.review_status}/><Badge value={r.chain_status}/></div><p>{r.reason_text}</p><small>{r.reviewer_id} · {fmt(r.reviewed_at)}</small><TechnicalDetails><Hash value={r.review_tx_hash}/></TechnicalDetails></article>)}</div>
 <div className="close-section"><h3>사건 종결 조건</h3>{item.status==='CLOSED'?<><Done>{mock?'종결 완료 · 로컬':'서버에서 종결된 사건'}</Done><p>{item.close_reason}</p><p className="caption">{fmt(item.closed_at)}</p></>:<>{item.close_eligible?<Done>현재 최신 검증과 관리자 승인 조건이 충족되었습니다.</Done>:<ul className="blocker-list">{item.close_blockers.map(code=><li key={code}>{blockerLabel(code)===code?<><span>종결 조건이 충족되지 않았거나 상태를 확인할 수 없습니다.</span><TechnicalDetails title="조건 상세"><pre className="json-view">{code}</pre></TechnicalDetails></>:blockerLabel(code)}</li>)}</ul>}<label>종결 사유<textarea aria-label="종결 사유" className="team-input" rows={2} value={closeReason} onChange={e=>setCloseReason(e.target.value)} maxLength={1000} disabled={busy||role!=='ADMIN'}/></label><button className="full-width" disabled={busy||!item.close_eligible||role!=='ADMIN'||!system?.capabilities.close_case||!closeReason.trim()} onClick={()=>void close()}>{system?.capabilities.close_case?'사건 종결':'사건 종결 · 조건 미충족'}</button></>}
 </div>
 </Panel>
}
