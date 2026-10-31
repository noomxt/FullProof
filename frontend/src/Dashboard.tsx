import {caseCatalog} from './caseCatalog';
import {OperationError} from './Details';
import {caseTitle,caseReference} from './presentation';
import {useContext,useEffect,useState} from 'react';
import {Link,useNavigate} from 'react-router-dom';
import {ArrowRight,ArrowUpRight,Check,CheckCircle2,ChevronRight,FileCheck2,FileText,Fingerprint,FolderOpen,Layers3,LoaderCircle,RefreshCw,Search,ShieldCheck,UploadCloud,Clock3} from 'lucide-react';
import {api,fmt,isMockMode,isRecorded,short} from './api';
import type {Case,Role} from './api';
import {Session} from './session';
import {caseLink,latestVerifications,roleInfo} from './roles';
import {Badge,Empty,Loading,Notice} from './ui';

const scenarios=caseCatalog.map(c=>({...c,text:c.note,icon:FolderOpen}));

function statusFor(c:Case,role:Role){
 if(c.status==='CLOSED')return {title:'종결',note:'기록·증빙 이력 보존',value:'CLOSED'};
 const v=c.verifications.at(-1);
 if(role==='AGENCY')return c.proofs.some(p=>isRecorded(p.chain_status))?{title:'증빙 제공 완료',note:'서명된 원천 증빙 보관',value:'CONFIRMED'}:{title:c.proofs.length?'서명 대기':'증빙 준비',note:c.proofs.length?'기존 초안을 이어서 서명':'기관 증빙 발급 준비',value:'PENDING'};
 if(role==='ADMIN')return !v?{title:'검증 전',note:'수사담당자 검증 요청 대기',value:'PENDING'}:v.freshness_status!=='CURRENT'?{title:'재검증 필요',note:'최신 입력 기준 재확인',value:'NEEDS_REVERIFICATION'}:v.review_status==='ACCEPTED'?{title:'승인 완료',note:c.close_eligible?'종결 조건 충족':'나머지 종결 조건 확인',value:'ACCEPTED'}:{title:'검토 필요',note:'판정과 원천 근거 확인',value:v.verdict||'PENDING'};
 return !c.claims.length?{title:'원문 등록',note:'수사 진행 기록부터 시작',value:'PENDING'}:!c.claims.at(-1)?.structured_claim?{title:'AI 구조화',note:'행동·대상·시각 추출',value:'PENDING'}:!v?{title:'증빙 연결·검증',note:'원천기관 자료 비교',value:'PENDING'}:{title:'검증 결과 확인',note:v.freshness_status==='CURRENT'?'최신 입력 기준':'입력 변경·재검증 필요',value:v.freshness_status==='CURRENT'?v.verdict||'PENDING':'NEEDS_REVERIFICATION'};
}
export default function Dashboard(){
 const {role,system}=useContext(Session),info=roleInfo[role],navigate=useNavigate();
 const [cases,setCases]=useState<Case[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[query,setQuery]=useState(''),[filter,setFilter]=useState('ALL'),[region,setRegion]=useState('ALL'),[scenario,setScenario]=useState('supported'),[opening,setOpening]=useState(false),[fresh,setFresh]=useState(false),[workOnly,setWorkOnly]=useState(false);
 async function refresh(){setLoading(true);setError('');try{setCases(await api<Case[]>('/api/v1/cases'))}catch(e){setError(e instanceof Error?e.message:'사건 조회 실패')}finally{setLoading(false)}}
 useEffect(()=>{setWorkOnly(false);void refresh()},[role]);
 async function openScenario(){
  setOpening(true);setError('');window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:true}));
  try{
   const existing=cases.filter(c=>c.scenario_id===scenario&&c.status!=='CLOSED').at(-1);
   if(existing&&!fresh){navigate(caseLink(role,existing.case_id));return}
   const c=await api<Case>('/api/v1/cases',{title:scenarios.find(s=>s.id===scenario)!.number+' · '+scenarios.find(s=>s.id===scenario)!.title,scenario_id:scenario});navigate(caseLink(role,c.case_id));
  }catch(e){setError(e instanceof Error?e.message:'사건을 열지 못했습니다.');await refresh()}finally{setOpening(false);window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:false}))}
 }
 const latest=latestVerifications(cases),proofs=cases.flatMap(c=>c.proofs),pendingReviews=latest.filter(v=>v.review_status==='PENDING'),openCases=cases.filter(c=>c.status!=='CLOSED');
 const stats=role==='OFFICER'?[
  {name:'전체 사건',count:cases.length,note:'현재 등록된 사건',icon:FolderOpen,unit:'건'},
  {name:'진행 중 사건',count:openCases.length,note:'종결 전 업무 대상 사건',icon:Clock3,unit:'건'},
  {name:'증빙이 뒷받침하는 검증',count:latest.filter(v=>v.verdict==='SUPPORTED').length,note:'최신 검증 기준 · 종결 사건 포함',icon:CheckCircle2,unit:'건'},
  {name:'추가 확인 필요 검증',count:latest.filter(v=>v.verdict==='CONTRADICTED'||v.verdict==='INSUFFICIENT').length,note:'충돌·근거 부족 · 종결 사건 포함',icon:Search,unit:'건'}
 ]:role==='AGENCY'?[
  {name:'증빙 제공 대상 사건',count:openCases.filter(c=>c.claims.length>0).length,note:'수사 기록이 등록된 사건',icon:FolderOpen,unit:'건'},
  {name:'서명 대기 초안',count:proofs.filter(p=>p.chain_status==='PENDING').length,note:'이미 만든 초안을 이어서 서명',icon:FileText,unit:'건'},
  {name:'제공 확인 증빙',count:proofs.filter(p=>isRecorded(p.chain_status)).length,note:'서명·기록 확인된 기관 Proof',icon:FileCheck2,unit:'건'},
  {name:'상태 확인 필요',count:proofs.filter(p=>['FAILED','UNKNOWN'].includes(p.chain_status)).length,note:'기존 기록 상태부터 확인',icon:Search,unit:'건'}
 ]:[
  {name:'검토 대기 검증',count:pendingReviews.length,note:'최신 검증 중 관리자 미확인',icon:Clock3,unit:'건'},
  {name:'보완 확인 필요',count:latest.filter(v=>v.verdict==='CONTRADICTED'||v.verdict==='INSUFFICIENT').length,note:'일치 여부와 근거를 함께 검토',icon:Search,unit:'건'},
  {name:'종결 가능 사건',count:openCases.filter(c=>c.close_eligible).length,note:'서버가 종결 조건 충족을 확인',icon:ShieldCheck,unit:'건'},
  {name:'종결 사건',count:cases.filter(c=>c.status==='CLOSED').length,note:'확인·승인 이력이 보존된 사건',icon:FileCheck2,unit:'건'}
 ];
 const rows=cases.filter(c=>(caseTitle(c.title)+' '+caseReference(c.case_id)+' '+c.case_id).toLowerCase().includes(query.toLowerCase())&&(filter==='ALL'||c.status===filter)&&(region==='ALL'||c.region===region)&&(!workOnly||(role==='AGENCY'?c.status!=='CLOSED'&&c.claims.length>0&&!c.proofs.some(p=>isRecorded(p.chain_status)):role==='ADMIN'?c.status!=='CLOSED'&&c.verifications.some(v=>v.freshness_status==='CURRENT'&&v.review_status!=='ACCEPTED'):c.status!=='CLOSED')));
 const activities=(role==='AGENCY'?cases.flatMap(c=>c.proofs.filter(p=>isRecorded(p.chain_status)).map(p=>({id:p.proof_id,case:c,title:'기관 증빙 제공',detail:p.call_id,date:p.proof_issued_at,value:p.chain_status}))):cases.flatMap(c=>c.verifications.map(v=>({id:v.verification_id,case:c,title:role==='ADMIN'?'검토 대상 검증':'수사행위 검증',detail:v.reason_text,date:v.created_at,value:v.verdict||v.processing_status})))).sort((a,b)=>(b.date||'').localeCompare(a.date||'')).slice(0,4);
 return <>
  <div className="page-title dashboard-title"><div><span className="eyebrow">WORKSPACE / {info.english}</span><h1 tabIndex={-1}>{info.title}</h1><p className="muted">{info.description}</p></div><button disabled={loading} onClick={()=>void refresh()}><RefreshCw size={15} className={loading?'spin':''}/>새로고침</button></div>
  <div className="workspace-intro"><div className="intro-copy"><span className="intro-kicker"><span/> {info.name} WORKSPACE</span><h2>{info.focus}</h2><p>{info.hint}</p><a href="#case-list" className="intro-link">{role==='AGENCY'?'제공 대상 확인':role==='ADMIN'?'검토 목록 확인':'사건 업무 시작'}<ArrowUpRight size={16}/></a></div><div className="workspace-art" aria-hidden="true"><img src={'/art/'+role.toLowerCase()+'.webp'} alt=""/></div></div>
  <div className="stats">{stats.map((s,i)=><div className={'stat stat-'+i} key={s.name}><div>{s.name}<s.icon size={18}/></div><strong>{s.count}<small>{s.unit}</small></strong><p>{s.note}</p></div>)}</div>
  {error&&<OperationError message={error}/>}
  {role==='OFFICER'&&<details className="new-case scenario-picker"><summary><Layers3 size={17}/>사건 선택하기<span>사건별 기록과 진행 현황<ChevronRight size={16}/></span></summary><div className="scenario-body"><div className="section-title"><div><h2>업무를 진행할 사건을 선택하세요.</h2><p>진행 중인 같은 사례가 있으면 이어서 엽니다.</p></div></div><div className="scenario-cards">{scenarios.map(s=><button key={s.id} className={scenario===s.id?'scenario-card selected':'scenario-card'} aria-pressed={scenario===s.id} aria-label={s.number+' '+s.title} disabled={opening} onClick={()=>setScenario(s.id)}><div><span>{s.number}</span>{scenario===s.id?<Check size={16}/>:<s.icon size={17}/>}</div><strong>{s.title}</strong><p>{s.text}</p></button>)}</div><div className="scenario-footer"><label><input type="checkbox" checked={fresh} disabled={opening} onChange={e=>setFresh(e.target.checked)}/>새 사건으로 등록</label><button className="primary" disabled={opening||loading||(!isMockMode()&&!system?.chain.available)} onClick={()=>void openScenario()}>{opening?<LoaderCircle className="spin" size={16}/>:<ArrowRight size={16}/>}선택한 사건 열기</button></div><p className="caption">진행 중인 같은 사례가 없거나 새 사건 등록을 선택하면 새 사건과 필수 단계를 등록합니다. 기존 기록은 보존됩니다.</p></div></details>}
  <div className="dashboard-columns"><section className="panel case-list-panel" id="case-list"><div className="panel-heading"><div><span className="eyebrow">{role==='AGENCY'?'EVIDENCE QUEUE':role==='ADMIN'?'REVIEW QUEUE':'CASE DIRECTORY'}</span><h2>{role==='AGENCY'?'증빙 요청 대상 사건':role==='ADMIN'?'검토 대상 사건':'사건 목록'} <span className="count-chip">{rows.length}</span></h2></div><div className="list-switch"><button aria-pressed={!workOnly} onClick={()=>setWorkOnly(false)}>전체</button><button aria-pressed={workOnly} onClick={()=>setWorkOnly(true)}>{role==='AGENCY'?'제공 대기':role==='ADMIN'?'검토 필요':'진행 중'}</button></div></div><div className="filters"><div className="search"><Search size={16}/><input aria-label="사건 검색" placeholder="사건명 또는 사건 ID 검색" value={query} onChange={e=>setQuery(e.target.value)}/></div><select aria-label="지역 필터" value={region} onChange={e=>setRegion(e.target.value)}><option value="ALL">전체 지역</option>{[...new Set(cases.map(c=>c.region).filter(Boolean))].map(r=><option key={r} value={r}>{r}</option>)}</select><select aria-label="진행 상태" value={filter} onChange={e=>setFilter(e.target.value)}><option value="ALL">전체 상태</option><option value="OPEN">진행 중</option><option value="CLOSED">종결</option></select></div>
   {loading?<Loading/>:!rows.length?<Empty>{role==='OFFICER'?'등록된 사건이 없습니다. 사건을 선택해 업무를 시작하세요.':'배정된 사건이 없습니다. 수사담당자의 사건 등록을 확인하세요.'}</Empty>:<div className="table-wrap"><table><thead><tr><th>사건 정보</th><th>사건 상태</th><th>{role==='AGENCY'?'증빙 제공 업무':role==='ADMIN'?'검토 업무':'다음 업무'}</th><th>열기</th></tr></thead><tbody>{rows.map(c=>{const state=statusFor(c,role);return <tr key={c.case_id}><td><Link className="case-name" to={caseLink(role,c.case_id)}><span className="case-folder">{role==='OFFICER'?<FolderOpen size={17}/>:<FileText size={17}/>}</span>{caseTitle(c.title)}</Link><p className="case-id">{caseReference(c.case_id)}</p></td><td><Badge value={c.status}/></td><td><span className="next-work">{state.title}</span><p>{state.note}</p></td><td><Link className="open-case" aria-label={caseTitle(c.title)+' 열기'} to={caseLink(role,c.case_id)}><ArrowUpRight size={17}/></Link></td></tr>})}</tbody></table></div>}
  </section><aside className="dashboard-rail"><section className="panel"><div className="panel-heading"><h2>{role==='AGENCY'?'최근 제공 활동':'최근 검증 활동'}</h2><span className="live-dot"/></div>{!activities.length?<div className="rail-empty"><Clock3 size={21}/><strong>아직 처리 이력이 없습니다</strong><p>업무를 진행하면 최근 활동이 여기에 표시됩니다.</p></div>:activities.map(a=><Link className="activity-item" key={a.id} to={caseLink(role,a.case.case_id)}><span className="activity-point"/><div><strong>{a.title}</strong><p>{caseTitle(a.case.title)}</p><Badge value={a.value}/><small>{fmt(a.date)}</small></div></Link>)}</section><div className="guide-note"><ShieldCheck size={22}/><strong>{role==='AGENCY'?'기관은 증빙에만 서명합니다':role==='ADMIN'?'판정과 승인은 별도입니다':'검증은 판단을 돕는 근거입니다'}</strong><p>{role==='AGENCY'?'자료 제공은 실제 열람을 증명하지 않습니다. 증빙이 확인하는 행위의 범위만 기록하세요.':role==='ADMIN'?'SUPPORTED는 자동 승인이 아닙니다. 최신 원문과 증빙, 검증 근거를 확인하세요.':'AI는 기록을 구조화하고 Rule Engine은 증빙을 비교합니다. 최종 업무 판단은 담당자가 수행합니다.'}</p><span>FULLPROOF PRINCIPLE</span></div></aside></div>
 </>;
}

export function AgencyHistory(){
 const [cases,setCases]=useState<Case[]>([]),[error,setError]=useState('');
 useEffect(()=>{void api<Case[]>('/api/v1/cases').then(setCases).catch(e=>setError(e.message))},[]);
 const rows=cases.flatMap(c=>c.proofs.map(p=>({c,p})));
 return <><div className="page-title"><div><span className="eyebrow">EVIDENCE / AUDIT TRAIL</span><h1 tabIndex={-1}>기관 증빙 제공 이력</h1><p className="muted">기관 증빙의 발급·서명·기록 상태를 확인합니다.</p></div></div>{error&&<OperationError message={error}/>}<section className="panel"><div className="panel-heading"><h2>증빙 목록</h2><span className="count-chip">{rows.length}</span></div>{!rows.length?<Empty>제공한 증빙이 없습니다.</Empty>:<div className="table-wrap"><table><thead><tr><th>사건·통화</th><th>발급 시각</th><th>기관 결과</th><th>기록 상태</th><th>열기</th></tr></thead><tbody>{rows.map(({c,p})=><tr key={p.proof_id+':'+p.proof_version}><td>{caseTitle(c.title)}<p>{p.call_id} · {short(p.proof_id)}</p></td><td>{fmt(p.proof_issued_at)}</td><td><Badge value={p.result}/></td><td><Badge value={p.chain_status}/></td><td><Link className="text-link" to={caseLink('AGENCY',c.case_id)}>증빙 열기<ArrowRight size={14}/></Link></td></tr>)}</tbody></table></div>}</section></>;
}
