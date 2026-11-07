import {isMockMode} from './api';
import {useState} from 'react';
import type {ReactNode} from 'react';
import {AlertCircle,LoaderCircle,CheckCircle2,Clock3} from 'lucide-react';
const labels:Record<string,string>={PROCESSING:'검증 처리 중',VALIDATING_AND_COMPARING:'입력 확인·판정 처리',RESULT_READY:'판정 생성 · 거래 확인 대기',WAITING_RECEIPT:'거래 영수증 확인 중',STATUS_UNKNOWN:'거래 상태 확인 필요',RPC_STATUS_UNKNOWN:'RPC 상태 확인 필요',RECOVERY_REQUIRED:'기존 거래 복구 확인 필요',SERVER_RESTARTED:'서버 재시작 · 상태 확인 필요',CHAIN_RECORD_UNAVAILABLE:'현재 체인 기록 조회 불가',FAILED_BEFORE_SUBMISSION:'거래 제출 전 처리 실패',TRANSACTION_REVERTED:'거래 실행 실패',EXTRACTION_OR_DECISION_FAILED:'추출·판정 처리 실패',MOCK:'가상 기록 · 온체인 미저장',SUPPORTED:'일치 · 증빙 뒷받침',CONTRADICTED:'불일치 · 충돌 발견',INSUFFICIENT:'근거 부족',PENDING:'대기',SUBMITTED:'거래 제출됨',CONFIRMED:'기록 확인 완료',FAILED:'처리 실패',UNKNOWN:'상태 확인 필요',CURRENT:'최신 입력 기준',NEEDS_REVERIFICATION:'재검증 필요',COMPLETED:'처리 완료',NEEDS_REVIEW:'추가 확인 필요',ACKNOWLEDGED:'확인됨',ACCEPTED:'단계 완료 승인',REVISION_REQUESTED:'보완 요청',OPEN:'진행 중',CLOSED:'종결',SUCCESS:'통화 성공',FAIL:'연결 실패',CALL_CONNECTED:'연결 성공',CALL_FAILED:'연결 실패',PHONE_CALL:'전화 통화'};
export const label=(s:string)=>labels[s]||s;
export function Badge({value,text}:{value:string;text?:string}){return <span className={'badge '+(['SUPPORTED','CONFIRMED','CURRENT','ACCEPTED','COMPLETED','SUCCESS','CALL_CONNECTED'].includes(value)?'green':['CONTRADICTED','FAILED','FAIL','CALL_FAILED'].includes(value)?'red':['INSUFFICIENT','NEEDS_REVIEW','NEEDS_REVERIFICATION','UNKNOWN'].includes(value)?'amber':'blue')}>{text||label(value)}</span>}
export function Panel({title,children,side}:{title:string;children:ReactNode;side?:ReactNode}){return <section className="panel"><div className="panel-heading"><h2>{title}</h2>{side}</div><div className="pane-body">{children}</div></section>}
function friendlyError(raw:string){
 if(/no verification/i.test(raw))return '최신 검증 결과가 없어 사건을 종결할 수 없습니다. 먼저 자동 검증을 완료해 주세요.';
 if(/not approved/i.test(raw))return '관리자 승인 후 사건을 종결할 수 있습니다.';
 if(/user rejected|user denied/i.test(raw))return '지갑에서 서명을 취소했습니다.';
 if(/registered signer|invalid signer|unauthorized/i.test(raw))return '현재 역할에 등록된 계정과 권한을 확인해 주세요.';
 if(/failed to fetch|networkerror|connection refused|timeout/i.test(raw))return '서버 또는 지갑 연결을 확인한 뒤 처리 상태를 다시 조회해 주세요.';
 if(/^[가-힣][^\n]{0,149}$/.test(raw)&&!/(?:0x[0-9a-f]{12,}|error|exception|revert|traceback|https?:)/i.test(raw))return raw;
 return '요청을 완료하지 못했습니다. 처리 상태를 확인해 주세요.';
}
export function Notice({children,error=false}:{children:ReactNode;error?:boolean}){
 const raw=error&&typeof children==='string'?children:null;
 const message=raw?friendlyError(raw):children;
 return <div className={'scope-note '+(error?'notice-error':'')} role={error?'alert':'note'}><AlertCircle size={18}/><div>{message}{raw&&message!==raw&&<details><summary>기술 상세</summary><pre className="json-view">{raw}</pre></details>}</div></div>;
}
export function Loading(){return <div className="state" role="status"><LoaderCircle className="spin" size={22}/>데이터를 불러오는 중입니다.</div>}
export function Empty({children}:{children:ReactNode}){return <div className="state"><Clock3 size={20}/>{children}</div>}
export function Hash({value}:{value:string|null|undefined}){
 const [message,setMessage]=useState('');
 if(!value)return <code className="hash">{isMockMode()?'가상 기록':'아직 생성되지 않음'}</code>;
 if(value.length<=22)return <code className="hash">{value}</code>;
 async function copy(){
  try{await navigator.clipboard.writeText(value!);setMessage('복사됨')}
  catch{setMessage('아래 원문을 선택해 복사해 주세요.')}
 }
 return <details className="record-detail"><summary><code>{value.slice(0,10)}…{value.slice(-6)}</code></summary><code className="hash">{value}</code><button type="button" onClick={()=>void copy()}>복사</button>{message&&<small role="status">{message}</small>}</details>;
}
export function Done({children}:{children:ReactNode}){return <div className="done" role="status"><CheckCircle2 size={17}/>{children}</div>}
