import {isMockMode} from './api';
import type {ReactNode} from 'react';
import {AlertCircle,LoaderCircle,CheckCircle2,Clock3} from 'lucide-react';
const labels:Record<string,string>={MOCK:'가상 기록 · 온체인 미저장',SUPPORTED:'일치 · 증빙 뒷받침',CONTRADICTED:'불일치 · 충돌 발견',INSUFFICIENT:'근거 부족',PENDING:'대기',SUBMITTED:'거래 제출됨',CONFIRMED:'기록 확인 완료',FAILED:'처리 실패',UNKNOWN:'상태 확인 필요',CURRENT:'최신 입력 기준',NEEDS_REVERIFICATION:'재검증 필요',COMPLETED:'처리 완료',NEEDS_REVIEW:'추가 확인 필요',ACKNOWLEDGED:'확인됨',ACCEPTED:'단계 완료 승인',REVISION_REQUESTED:'보완 요청',OPEN:'진행 중',CLOSED:'종결',SUCCESS:'통화 성공',FAIL:'연결 실패',CALL_CONNECTED:'연결 성공',CALL_FAILED:'연결 실패',PHONE_CALL:'전화 통화'};
export const label=(s:string)=>labels[s]||s;
export function Badge({value,text}:{value:string;text?:string}){return <span className={'badge '+(['SUPPORTED','CONFIRMED','CURRENT','ACCEPTED','COMPLETED','SUCCESS','CALL_CONNECTED'].includes(value)?'green':['CONTRADICTED','FAILED','FAIL','CALL_FAILED'].includes(value)?'red':['INSUFFICIENT','NEEDS_REVIEW','NEEDS_REVERIFICATION','UNKNOWN'].includes(value)?'amber':'blue')}>{text||label(value)}</span>}
export function Panel({title,children,side}:{title:string;children:ReactNode;side?:ReactNode}){return <section className="panel"><div className="panel-heading"><h2>{title}</h2>{side}</div><div className="pane-body">{children}</div></section>}
export function Notice({children,error=false}:{children:ReactNode;error?:boolean}){return <div className={'scope-note '+(error?'notice-error':'')} role={error?'alert':'note'}><AlertCircle size={18}/><div>{children}</div></div>}
export function Loading(){return <div className="state" role="status"><LoaderCircle className="spin" size={22}/>데이터를 불러오는 중입니다.</div>}
export function Empty({children}:{children:ReactNode}){return <div className="state"><Clock3 size={20}/>{children}</div>}
export function Hash({value}:{value:string|null|undefined}){return <code className="hash" title={value||''}>{value||(isMockMode()?'실제 거래 없음 · 가상 처리':'아직 생성되지 않음')}</code>}
export function Done({children}:{children:ReactNode}){return <div className="done" role="status"><CheckCircle2 size={17}/>{children}</div>}
