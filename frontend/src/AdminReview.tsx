import {useEffect,useState} from 'react';
import {api,fmt,isMockMode} from './api';
import type {Case,Review,Role,System} from './api';
import {Badge,Empty,Hash,Notice,Panel,Done,label} from './ui';

export const blockerLabel=(code:string)=>({CASE_ALREADY_CLOSED:'이미 종결된 사건입니다.',CLAIM_NOT_ANCHORED:'최신 수사기록 원문 기록이 필요합니다.',VERIFICATION_PENDING:'최신 검증 결과가 없어 사건을 종결할 수 없습니다. 먼저 자동 검증을 완료해 주세요.',NEEDS_REVERIFICATION:'입력이 변경되어 재검증이 필요합니다.',VERIFICATION_CONTRADICTED:'불일치 항목을 보완해야 합니다.',VERIFICATION_INSUFFICIENT:'검증할 증빙·연결 근거가 부족합니다.',PROOF_MISSING:'연결된 기관 제출 증빙가 없습니다.',ADMIN_REVIEW_PENDING:'최신 검증에 대한 관리자 확인이 필요합니다.',ADMIN_REVIEW_NOT_ACCEPTED:'최신 검증에 대한 단계 완료 승인이 필요합니다.',ADMIN_REVIEW_NOT_IMPLEMENTED:'관리자 이력 API 연결 대기',V11_CLOSE_CONTRACT_NOT_IMPLEMENTED:'v1.1 종결 컨트랙트 연결 대기'} as Record<string,string>)[code]||(/no verification/i.test(code)?'최신 검증 결과가 없어 사건을 종결할 수 없습니다. 먼저 자동 검증을 완료해 주세요.':'종결 조건을 확인하지 못했습니다. 사건 상태를 새로고침해 주세요.');

export default function AdminReview({item,system,role,onChange,section}:{item:Case;system:System|null;role:Role;onChange:()=>Promise<void>;section:"admin"|"close"}){
 const v=item.verifications.at(-1),mock=isMockMode();
 const [status,setStatus]=useState('ACKNOWLEDGED'),[reason,setReason]=useState(''),[closeReason,setCloseReason]=useState(''),[rows,setRows]=useState<Review[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 async function load(){if(!v){setRows([]);return}const result=await api<{items:Review[]}>('/api/v1/verifications/'+v.verification_id+'/reviews');setRows(result.items)}
 useEffect(()=>{if(section!=='admin')return;void load().catch(e=>setError(e.message));setMessage('');setStatus('ACKNOWLEDGED')},[v?.verification_id,section]);
 const editable=role==='ADMIN'&&item.status==='OPEN'&&v?.freshness_status==='CURRENT'&&(mock||v.chain_status==='CONFIRMED');
 const acceptable=v?.verdict==='SUPPORTED'&&v.freshness_status==='CURRENT'&&(mock||v.chain_status==='CONFIRMED');
 async function saveReview(){setBusy(true);document.documentElement.dataset.fullproofBusy='true';window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:true}));setError('');setMessage('');try{await api('/api/v1/verifications/'+v!.verification_id+'/reviews',{review_status:status,reason_text:reason,verification_hash:v!.verification_hash});await onChange();await load();setReason('');setMessage(mock?'관리자 확인을 가상 이력으로 저장했습니다. 실제 온체인 기록은 없습니다.':'관리자 확인 요청을 처리했습니다. 기록 상태를 확인하십시오.')}catch(e){setError(e instanceof Error?e.message:'처리 실패')}finally{setBusy(false);delete document.documentElement.dataset.fullproofBusy;window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:false}))}}
 async function close(){setBusy(true);document.documentElement.dataset.fullproofBusy='true';window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:true}));setError('');setMessage('');try{await api('/api/v1/cases/'+item.case_id+'/close',{reason_text:closeReason});await onChange();setMessage(mock?'가상 사건을 종결했습니다. 실제 경찰 시스템의 사건은 변경하지 않습니다.':'종결 요청을 처리했습니다. 서버 처리 결과를 확인하십시오.')}catch(e){setError(e instanceof Error?e.message:'종결 실패')}finally{setBusy(false);delete document.documentElement.dataset.fullproofBusy;window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:false}))}}
 return <Panel title={section==="admin"?"06 · 관리자 검토·승인":"07 · 사건 종결"} side={item.status==='CLOSED'?<Badge value="CLOSED"/>:undefined}>
 <Notice>{mock?'프론트엔드 가상 처리입니다. 관리자 확인·판정·종결 이력은 서로 분리되며 실제 서명·거래를 만들지 않습니다.':'관리자 지갑의 메시지 서명 후 백엔드가 승인·종결 거래를 제출합니다. 서명을 취소하면 요청을 제출하지 않습니다.'}</Notice>
 {error&&<Notice error>{error}</Notice>}{message&&<Done>{message}</Done>}
 {role!=='ADMIN'&&<p className="caption">업무 설정에서 관리자 역할을 선택하여 확인·보완·승인을 처리하십시오.</p>}
 {section==="admin"&&<>{v&&<p className="caption">대상 검증 <Hash value={v.verification_id}/><br/>원문 v{v.claim_ref.claim_version} · <Badge value={v.freshness_status}/></p>}
 <label>관리자 처리<select className="full-width spaced" aria-label="관리자 처리" value={status} onChange={e=>setStatus(e.target.value)} disabled={busy||!editable}><option value="ACKNOWLEDGED">결과 확인</option><option value="REVISION_REQUESTED">보완 요청</option><option value="ACCEPTED" disabled={!acceptable}>단계 완료 승인</option></select></label>
 <label>확인·보완 사유<textarea aria-label="관리자 사유" className="team-input" value={reason} onChange={e=>setReason(e.target.value)} rows={2} maxLength={1000} disabled={busy||!editable}/></label>
 <button className="primary" disabled={busy||!editable||!system?.capabilities.admin_review||!reason.trim()||(status==='ACCEPTED'&&!acceptable)} onClick={()=>void saveReview()}>{busy?'처리 중…':system?.capabilities.admin_review?'관리자 확인 기록':'관리자 확인 기록 · 연결 대기'}</button>
 <p className="caption">결과 확인은 완료 승인이 아닙니다. 불일치·근거 부족·재검증 필요 상태는 단계 완료를 승인할 수 없습니다.</p>
 <div className="review-history"><h3>최신 검증의 관리자 확인 이력</h3>{!rows.length?<Empty>관리자 검토 이력이 없습니다.</Empty>:rows.map(r=><article className="review-row" key={r.review_id}><div><Badge value={r.review_status}/><Badge value={r.chain_status}/></div><p>{r.reason_text}</p><small>{r.reviewer_id} · {fmt(r.reviewed_at)}</small><Hash value={r.review_tx_hash}/></article>)}</div>
 </>}
 {section==="close"&&<><div className="close-section"><h3>사건 종결 조건</h3>{item.status==='CLOSED'?<><Done>{mock?'가상 사건 종결 완료':'서버에서 종결된 사건'}</Done><p>{item.close_reason}</p><p className="caption">{fmt(item.closed_at)}</p></>:<>{item.close_eligible?<Done>현재 최신 검증과 관리자 승인 조건이 충족되었습니다.</Done>:<ul className="blocker-list">{item.close_blockers.map(code=><li key={code}>{blockerLabel(code)}{/(?:exception|revert|cannot close|error|^\()/i.test(code)&&<details><summary>기술 상세</summary><pre className="json-view">{code}</pre></details>}</li>)}</ul>}<label>종결 사유<textarea aria-label="종결 사유" className="team-input" rows={2} value={closeReason} onChange={e=>setCloseReason(e.target.value)} maxLength={1000} disabled={busy||role!=='ADMIN'}/></label><button className="full-width" disabled={busy||!item.close_eligible||role!=='ADMIN'||!system?.capabilities.close_case||!closeReason.trim()} onClick={()=>void close()}>{system?.capabilities.close_case?'사건 종결':'사건 종결 · 조건 미충족'}</button></>}
 </div>
 <div className="procedure-note" role="note"><strong>{item.status==='CLOSED'?'처리 완료 · 사건 종결':'후속 처리 안내'}</strong><p>{item.status==='CLOSED'?'종결 사유 및 처리 이력은 사건 이력 화면에서 조회할 수 있습니다.':item.close_eligible?'종결 요건이 충족되었습니다. 관리자는 종결 사유를 입력한 후 사건 종결을 처리하십시오.':'검증 결과 및 종결 조건을 확인하십시오. 보완이 필요한 경우 사유를 기록하여 수사담당자에게 확인을 요청하고, 최신 검증에 대한 승인 후 종결 요건을 재확인하십시오.'}</p></div>
 </>}
 </Panel>
}
