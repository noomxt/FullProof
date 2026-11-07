import type {ReactNode} from 'react';
import type {IntegrityReport} from './integrity';
import EvidenceDeadlines from './EvidenceDeadlines';
import './workflow.css';
import WorkflowCheck from './WorkflowCheck';
import Home from './Home';
import BrandLogo from './BrandLogo';
import StartupSplash from './StartupSplash';
import ProcedureNote from './ProcedureNote';
import { randomUUID } from './uuid';
import {createContext,useContext,useEffect,useRef,useState} from 'react';
import {Link,NavLink,Route,Routes,useNavigate,useParams,useSearchParams,useLocation} from 'react-router-dom';
import {ArrowRight,ArrowLeft,ShieldCheck,LayoutDashboard,History,RefreshCw,Database,FileText,CheckCircle2,Search,LockKeyhole,ChevronRight,Plus,LoaderCircle} from 'lucide-react';
import {api,setRole,signProof,fmt,short,ApiError,isMockMode,setApiMode,isRecorded} from './api';
import type {Case,Claim,Proof,Verification,Draft,Role,System,Transaction,VerificationRequest} from './api';
import AdminReview from './AdminReview';
import IntegrityPanel from './IntegrityPanel';
import MockTools from './MockTools';
import ThemeToggle from './ThemeToggle';
import {waitForVerification} from './verificationRequests';
import {Badge,Panel,Notice,Loading,Empty,Hash,Done,label} from './ui';

const Session=createContext<{role:Role;system:System|null}>({role:'OFFICER',system:null});
function errorText(e:unknown){return e instanceof Error?e.message:'처리 중 오류가 발생했습니다.'}

export default function App(){
 const navigate=useNavigate(),location=useLocation();const [mock,setMock]=useState(isMockMode());
 const [operationCount,setOperationCount]=useState(0);const operationBusy=operationCount>0;
 useEffect(()=>{const listen=(event:Event)=>setOperationCount(n=>Math.max(0,n+((event as CustomEvent<boolean>).detail?1:-1)));window.addEventListener('fullproof:busy',listen);return ()=>window.removeEventListener('fullproof:busy',listen)},[]);
 const [role,changeRole]=useState<Role>(()=>{const stored=localStorage.getItem('fullproof.demo.role');return ['OFFICER','AGENCY','ADMIN'].includes(stored||'')?stored as Role:'OFFICER'}),[ready,setReady]=useState(false),[system,setSystem]=useState<System|null>(null),[error,setError]=useState('');
 async function connect(next=role){setReady(false);setError('');try{await setRole(next);changeRole(next);setSystem(await api<System>('/api/v1/system/status'));setReady(true);return true}catch(e){setError(errorText(e));return false}}
 useEffect(()=>{void connect()},[]);
 if(location.pathname==='/')return <><StartupSplash/><Home onEnter={async next=>{const ok=await connect(next);if(ok)navigate('/workspace');return ok}}/></>;
 return <><StartupSplash/><Session.Provider value={{role,system}}><div className="app-shell full-width-workspace">
  <div className="workspace"><header className="topbar"><div className="workspace-heading"><Link to="/" className="workspace-home-logo" aria-label="FullProof 홈"><BrandLogo/></Link><span><strong>FullProof · 수사 업무</strong><small>수사했다는 기록을, 확인 가능한 증명으로</small></span></div><div><NavLink className="workspace-history-link" to="/history"><History size={14}/>검증·기록 이력</NavLink><ThemeToggle/><details className="settings"><summary>업무 설정</summary><div className="settings-content"><span className="demo-label">{mock?'FRONTEND MOCK':'TEAM API'} · v1.1</span><select aria-label="실행 모드" disabled={operationBusy} value={mock?'mock':'api'} onChange={e=>{if(document.documentElement.dataset.fullproofBusy){return}const next=e.target.value as 'mock'|'api';setApiMode(next);setMock(next==='mock');navigate('/');void connect('OFFICER')}}><option value="mock">프론트엔드 Mock</option><option value="api">서버 연결</option></select><label className="role-label">업무 역할 <select aria-label="업무 역할" value={role} disabled={operationBusy||(!ready&&!error)} onChange={e=>{if(document.documentElement.dataset.fullproofBusy){return}void connect(e.target.value as Role)}}><option value="OFFICER">수사 담당자</option><option value="AGENCY">원천기관</option><option value="ADMIN">관리자</option></select></label>{mock&&<MockTools/>}{!mock&&system&&<div className="settings-chain"><strong>{system.chain.available?'로컬 체인 연결됨':'로컬 체인 연결 필요'}</strong><p className="caption">체인 ID {system.chain.chain_id||'미확인'}</p><span>컨트랙트</span><Hash value={system.chain.contract_address}/><span>기관 서명 지갑</span><Hash value={system.chain.signer_address}/><span>관리자 지갑</span><Hash value={system.chain.admin_address}/><span>증빙 연결 담당자 지갑</span>{system.chain.reviewer_addresses?.map(a=><Hash key={a} value={a}/>)}</div>}<p className="caption">역할 선택은 화면 구분이며 실제 인증이 아닙니다.</p></div></details></div></header>
  <main>{error?<><Notice error>{error}</Notice><button onClick={()=>void connect()}>연결 재시도</button></>:!ready?<Loading/>:<Routes><Route path="/workspace" element={<Dashboard/>}/><Route path="/cases/:id" element={<CaseWorkspace key={role}/>}/><Route path="/integration" element={<Dashboard/>}/><Route path="/history" element={<HistoryPage/>}/><Route path="*" element={<Empty>페이지가 없습니다. <Link to="/workspace">사건 관리로 이동</Link></Empty>}/></Routes>}</main>
  <details className="demo-banner"><summary>평가 환경 안내 · 가상 자료 전용 <span>펼치기 / 접기</span></summary><p>대회 평가용 환경입니다. 모든 사건·증빙은 가상 자료이며 실제 경찰 시스템과 연결되지 않습니다. 호출과 거래의 완료 여부는 각 기록 상태에서 확인하십시오. 업무 선택은 로그인 및 권한 인증을 대신하지 않습니다. {mock?'현재 모드는 브라우저 가상 시연이며 실제 API·전자서명·블록체인을 호출하지 않습니다.':system?.ai.is_simulated?'현재 AI 구조화는 고정 응답을 사용합니다.':'AI 호출 결과는 사건별 구조화 화면에서 확인할 수 있습니다.'}</p></details>
  <footer>FullProof © 2026 <span>수사했다는 기록을, 확인 가능한 증명으로</span></footer></div>
 </div></Session.Provider></>
}

const evaluationCaseTitles:Record<string,string> = {
 supported: '강남역 안예원 실종사건',
 contradicted: '잠실역 백종수 실종 사건',
 insufficient: '성수역 이지연 실종 사건',
 ambiguous: '교대역 박진수 실종 사건',
};

function Dashboard(){
 const [emptyDeadlineTarget,setEmptyDeadlineTarget]=useState<HTMLDivElement|null>(null);
 const {role,system}=useContext(Session),navigate=useNavigate();
 const [cases,setCases]=useState<Case[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[query,setQuery]=useState(''),[filter,setFilter]=useState('ALL'),[region,setRegion]=useState('ALL'),[scenario,setScenario]=useState('supported'),[creating,setCreating]=useState(false),[needsOnly,setNeedsOnly]=useState(false);
 const roleName={OFFICER:'수사담당자',AGENCY:'원천기관',ADMIN:'관리자'}[role];
 async function refresh(){setLoading(true);setError('');try{setCases((await api<Case[]>('/api/v1/cases')).filter(c=>!['FP-minji-c0381340','FP-minji-e939277f','FP-minji-a5081590','FP-minji-751d6e3a'].includes(c.case_id)))}catch(e){setError(errorText(e))}finally{setLoading(false)}}
 useEffect(()=>{void refresh()},[role]);
 async function create(presentation=false){if(creating)return;setCreating(true);window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:true}));try{const c=await api<Case>('/api/v1/cases',{title:presentation?'삼성역 김민지 실종사건':evaluationCaseTitles[scenario],scenario_id:presentation?'minji':scenario});navigate('/cases/'+c.case_id)}catch(e){await refresh();setError(errorText(e))}finally{setCreating(false);window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:false}))}}
 const latest=(c:Case)=>c.verifications.filter(v=>v.freshness_status==='CURRENT').at(-1);
 const needs=(c:Case)=>{const v=latest(c);return !!v&&['CONTRADICTED','INSUFFICIENT'].includes(v.verdict||'')};
 const rows=cases.filter(c=>(c.title+' '+c.case_id).toLowerCase().includes(query.toLowerCase())&&(filter==='ALL'||c.status===filter)&&(region==='ALL'||c.region===region)&&(!needsOnly||needs(c)));
 function nextWork(c:Case){if(c.status==='CLOSED')return {name:'처리 이력 조회',tab:'history'};if(role==='AGENCY')return {name:c.proofs.some(p=>isRecorded(p.chain_status))?'제출 증빙 조회':'증빙 제출·전자서명',tab:'proofs'};if(role==='ADMIN')return {name:c.verifications.length?'검증 결과 검토':'검증 결과 대기',tab:'admin'};if(!c.claims.length)return {name:'수사기록 등록',tab:'records'};if(!c.claims.at(-1)?.structured_claim)return {name:'수사기록 구조화',tab:'structure'};if(!c.proofs.some(p=>isRecorded(p.chain_status))&&c.scenario_id!=='insufficient')return {name:'기관 증빙 제출 대기',tab:'proofs'};if(needs(c))return {name:'추가 확인 필요',tab:'verification'};if(c.verifications.length)return {name:'검증 결과 확인',tab:'verification'};return {name:'증빙 연결·검증',tab:'mapping'}}
 return <><div className="page-title"><div><span className="eyebrow">WORKSPACE / {role}</span><h1>{roleName} 업무 대시보드</h1><p className="muted">진행 사건 및 처리 대기 업무를 조회합니다.</p></div><button disabled={loading} onClick={()=>void refresh()}><RefreshCw size={16}/>새로고침</button></div>
 <div className="stats">{[{name:'전체 사건',count:cases.length,icon:FileText,note:'현재 등록된 사건'},{name:'진행 중 사건',count:cases.filter(c=>c.status==='OPEN').length,icon:Search,note:'종결 전 업무 대상 사건'},{name:'증빙이 뒷받침하는 검증',count:cases.filter(c=>latest(c)?.verdict==='SUPPORTED').length,icon:CheckCircle2,note:'사건별 최신 검증 기준'},{name:'추가 확인 필요',count:cases.filter(needs).length,icon:History,note:'불일치·근거 부족 사건'}].map((s,i)=><div className={'stat'+(i===3&&s.count>0?' stat-attention':'')} key={s.name}><div>{s.name}<s.icon size={20}/></div><strong>{loading?'—':s.count}<small>건</small></strong><p>{s.note}</p>{i===3&&s.count>0&&<button className="stat-action" onClick={()=>{
  setNeedsOnly(true);
  setQuery('');
  setFilter('ALL');
  setRegion('ALL');
  document.getElementById('case-list')?.scrollIntoView({behavior:'smooth',block:'start'});
}}>대상 사건 조회<ArrowRight size={13}/></button>}</div>)}</div>
 {error&&<Notice error>{error}</Notice>}
 <EvidenceDeadlines emptyTarget={emptyDeadlineTarget}/>
 <div className="dashboard-columns" style={{gridTemplateColumns:"minmax(0,1fr)"}}><section className="panel case-directory" id="case-list"><div className="panel-heading"><div><span className="eyebrow">CASE DIRECTORY</span><h2>사건 목록 <small>{rows.length}건</small></h2></div><div className="list-switch"><button aria-pressed={!needsOnly} onClick={()=>setNeedsOnly(false)}>전체</button><button aria-pressed={needsOnly} onClick={()=>setNeedsOnly(true)}>확인 필요</button></div></div><div className="filters"><div className="search"><Search size={17}/><input aria-label="사건 검색" placeholder="사건명 또는 사건 ID 검색" value={query} onChange={e=>setQuery(e.target.value)}/></div><select aria-label="지역 필터" value={region} onChange={e=>setRegion(e.target.value)}><option value="ALL">전체 지역</option>{[...new Set(cases.map(c=>c.region).filter(Boolean))].map(r=><option key={r} value={r}>{r}</option>)}</select><select aria-label="진행 상태" value={filter} onChange={e=>setFilter(e.target.value)}><option value="ALL">전체 상태</option><option value="OPEN">진행 중</option><option value="CLOSED">종결</option></select></div>
 {loading?<Loading/>:!rows.length?<Empty>조회된 사건이 없습니다.</Empty>:<div className="table-wrap"><table><thead><tr><th>사건 정보</th><th>사건 상태</th><th>다음 업무</th><th>열기</th></tr></thead><tbody>{rows.map(c=>{const next=nextWork(c);return <tr key={c.case_id}><td><Link className="text-link" to={'/cases/'+c.case_id+'?tab='+next.tab}>{c.title}</Link><p className="mono">{short(c.case_id)}</p></td><td><Badge value={c.status}/></td><td><strong className={needs(c)?'attention-text':''}>{next.name}</strong>{latest(c)&&<p><Badge value={latest(c)!.verdict||latest(c)!.processing_status}/></p>}</td><td><Link className="button open-case" aria-label={c.title+' 열기'} to={'/cases/'+c.case_id+'?tab='+next.tab}><ArrowRight size={16}/></Link></td></tr>})}</tbody></table></div>}</section>
 </div>
 <div className="case-registration-with-note" style={{display:'flex',gap:12,flexWrap:'wrap',alignItems:'flex-start'}}>
 {role==='OFFICER'&&<div style={{display:'flex',gap:12,flexWrap:'wrap',alignItems:'flex-start'}}><details className="new-case"><summary><Plus size={16}/>평가용 사건 등록</summary><Panel title="평가용 사건 등록" side={<span className="muted demo-disclosure">가상 통화 자료</span>}><div className="create-row"><label>평가 유형<select aria-label="평가 유형" value={scenario} onChange={e=>setScenario(e.target.value)}>{Object.entries(evaluationCaseTitles).map(([id,title])=><option key={id} value={id}>{title}</option>)}</select></label><button className="primary" disabled={creating||(!isMockMode()&&!system?.chain.available)} onClick={()=>void create()}>{creating?<LoaderCircle className="spin" size={16}/>:<Plus size={16}/>}사건 등록</button><span className="muted demo-disclosure">평가용 가상 사건을 등록합니다.</span></div></Panel></details><details className="new-case"><summary><Plus size={16}/>발표용 사건 등록</summary><Panel title="발표용 사건 등록"><div className="create-row"><strong>삼성역 김민지 실종사건</strong><button className="primary" disabled={creating||isMockMode()||!system?.chain.available} onClick={()=>void create(true)}>사건 등록</button></div>{isMockMode()&&<p className="caption">팀 API 모드에서 발표용 사건을 등록할 수 있습니다.</p>}</Panel></details></div>}
  <div style={{width:330,maxWidth:"100%"}}><section className="principle-note"><ShieldCheck size={22}/><h3>검증 결과 확인 시 유의사항</h3><p>자동 검증 결과는 제출된 기록과 증빙을 기준으로 산출됩니다. 담당자는 검증 근거를 확인한 후 후속 업무를 처리하여야 합니다.</p></section></div>
 </div>
 <p className="caption demo-disclosure">{isMockMode()?'브라우저 가상 시연 모드입니다. 실제 서명 및 거래는 실행하지 않습니다.':'서버에 등록된 평가용 사건을 조회합니다. 모든 사건·증빙은 가상 자료입니다.'}</p><div ref={setEmptyDeadlineTarget}/></>
}

function VerifiedAdminStage({verificationId,children}:{verificationId:string;children:ReactNode}){
 const mock=isMockMode();
 const [attempt,setAttempt]=useState(0);
 const [check,setCheck]=useState<'checking'|'passed'|'blocked'>('checking');
 useEffect(()=>{
  if(mock)return;
  let active=true;
  setCheck('checking');
  void api<IntegrityReport>('/api/v1/verifications/'+verificationId+'/integrity')
   .then(report=>{if(active)setCheck(report.ok?'passed':'blocked')})
   .catch(()=>{if(active)setCheck('blocked')});
  return ()=>{active=false};
 },[verificationId,attempt,mock]);
 if(mock||check==='passed')return <>{children}</>;
 if(check==='checking')return <Notice>관리자 단계에 앞서 원문·증빙·검증 해시를 확인하고 있습니다.</Notice>;
 return <><Notice error>관리자 단계로 진행할 수 없습니다. 해시가 일치하지 않거나 확인할 수 없습니다.</Notice><button onClick={()=>{setCheck('checking');setAttempt(n=>n+1)}}>해시 다시 확인</button></>;
}

function CaseWorkspace(){
 const {id}=useParams(),{role,system}=useContext(Session);
 const [newStepName,setNewStepName]=useState('');const [params,setParams]=useSearchParams();const requestedTab=params.get('tab')||'overview';const tab=['overview','records','structure','proofs','mapping','verification','history','admin','close'].includes(requestedTab)?requestedTab:'overview';const [stepId,setStepId]=useState(0);
 const tabs=[['records','원문 등록'],['structure','AI 구조화 확인'],['proofs','기관 증빙 제출·서명'],['mapping','증빙 연결'],['verification','자동 검증'],['admin','관리자 검토·승인'],['close','사건 종결']] as const;
 const go=(value:string)=>{if(document.documentElement.dataset.fullproofBusy)return;setParams(old=>{const next=new URLSearchParams(old);next.set('tab',value);return next});window.scrollTo({top:0,behavior:'instant'})};
 const [item,setItem]=useState<Case|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(''),[message,setMessage]=useState(''),[text,setText]=useState(''),[selectedClaim,setSelectedClaim]=useState(''),[selectedProof,setSelectedProof]=useState(''),[draft,setDraft]=useState<Draft|null>(null),[review,setReview]=useState('ACKNOWLEDGED'),[reason,setReason]=useState(''),[tx,setTx]=useState<Transaction|null>(null),[chainCounts,setChainCounts]=useState<Record<string,unknown>|null>(null),[serverResult,setServerResult]=useState<Partial<Verification>|null>(null);
 const [presentationCall,setPresentationCall]=useState('first');
 const [requestProgress,setRequestProgress]=useState<VerificationRequest|null>(null);
 useEffect(()=>{setRequestProgress(null);const listen=(event:Event)=>{const job=(event as CustomEvent<VerificationRequest>).detail;if(job.case_id===id)setRequestProgress(job)};window.addEventListener('fullproof:verification-request',listen);return ()=>window.removeEventListener('fullproof:verification-request',listen)},[id]);
 const verifyKey=useRef<string|null>(null);
 useEffect(()=>{verifyKey.current=null},[item?.claims.length,item?.proofs.filter(p=>isRecorded(p.chain_status)).length,item?.mappings.length]);
 async function refresh(){const c=await api<Case>('/api/v1/cases/'+id);setItem(c);setSelectedClaim(old=>old||(c.claims.length?c.claims.at(-1)!.claim_id+':'+c.claims.at(-1)!.claim_version:''));}
 useEffect(()=>{setText('');void refresh().catch(e=>setError(errorText(e)))},[id]);
 async function run(name:string,fn:()=>Promise<void>){setBusy(name);document.documentElement.dataset.fullproofBusy='true';window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:true}));setError('');setMessage('');try{await fn();await refresh()}catch(e){setError(errorText(e));try{await refresh()}catch{}}finally{setBusy('');delete document.documentElement.dataset.fullproofBusy;window.dispatchEvent(new CustomEvent('fullproof:busy',{detail:false}))}}
 if(!item)return error?<><Notice error>{error}</Notice><button onClick={()=>void run('새로고침',refresh)}>재시도</button></>:<Loading/>;
 const stepClaims=item.claims.filter(c=>c.step_id===stepId);const latest=stepClaims.at(-1),claim=stepClaims.find(c=>c.claim_id+':'+c.claim_version===selectedClaim)||latest;
 const current=claim===latest;
 const extraction=claim?.structured_claim,action=extraction?.actions[0];
 const mapping=[...item.mappings].reverse().find(m=>m.claim_id===claim?.claim_id&&m.claim_version===claim?.claim_version&&m.mapping_status==='CONFIRMED');
 const proof=item.proofs.find(p=>p.proof_id===(selectedProof||mapping?.proof_id)&&p.step_id===stepId);
 const verification=item.verifications.filter(v=>v.step_id===stepId).at(-1);
 const canOfficer=role==='OFFICER'&&item.status==='OPEN',canAgency=role==='AGENCY'&&item.status==='OPEN';
 const hasProof=item.proofs.some(p=>p.step_id===stepId&&isRecorded(p.chain_status));
 const fresh=verification?.freshness_status==='CURRENT';
 const steps=[
  claim&&isRecorded(claim.chain_status)?'완료':'대기',
  extraction?.extraction_status==='COMPLETED'?'완료':extraction&&extraction.extraction_status!=='PENDING'?'조치 필요':'대기',
  hasProof?'완료':fresh?'조치 필요':'대기',
  mapping?'완료':fresh?'조치 필요':'대기',
  fresh&&isRecorded(verification?.chain_status)?verification?.verdict==='SUPPORTED'?'완료':'조치 필요':verification?'조치 필요':'대기',
  fresh&&verification?.review_status==='ACCEPTED'?'완료':fresh&&verification?.verdict!=='SUPPORTED'?'차단':'대기',
  item.status==='CLOSED'?'완료':item.close_eligible?'대기':'차단',
 ];
 const requestRows=new Map((item.verification_requests||[]).map(r=>[r.verification_id,r]));
 if(requestProgress)requestRows.set(requestProgress.verification_id,requestProgress);
 const disabled=!!busy;
 const procedure=tab==='records'?{title:claim?'다음 절차 · 수사기록 구조화':'처리 사항 · 수사기록 등록',text:claim?'등록된 원문을 기준으로 구조화를 실행하십시오. 수정이 필요한 경우 새 버전으로 등록하여야 합니다.':'수행한 수사행위를 입력한 후 원문을 등록하십시오.',target:claim?'structure':null,action:'구조화 화면으로'}:tab==='structure'?{title:extraction?.extraction_status==='COMPLETED'?'다음 절차 · 원천기관 증빙 제출':'처리 사항 · 구조화 실행',text:extraction?.extraction_status==='COMPLETED'?'원천기관의 증빙 제출이 필요합니다. 기관 담당자가 증빙 발급 및 전자서명을 완료한 후 수사담당자가 대응 통화를 지정하십시오. 기관 증빙 미확보 사례는 검증 화면에서 근거 부족 결과를 기록할 수 있습니다.':'원문 등록 후 구조화를 실행하고 추출 결과를 확인하십시오.',target:extraction?.extraction_status==='COMPLETED'?'proofs':null,action:'기관 증빙 화면으로'}:tab==='proofs'?{title:'다음 절차 · 대응 통화 지정',text:item.proofs.some(p=>p.step_id===stepId&&isRecorded(p.chain_status))?'증빙 기록이 확인되었습니다. 수사담당자는 대상·시각·통화 식별번호를 대조하여 대응 통화를 지정하십시오.':'원천기관 담당자의 증빙 제출 및 전자서명이 필요합니다. 서명 후 거래 기록 상태를 확인하십시오. 기관 증빙 미확보 시 검증 화면에서 근거 부족 여부를 확인할 수 있습니다.',target:'mapping',action:'통화 연결 화면으로'}:tab==='mapping'?{title:mapping?'다음 절차 · 검증 실행':'처리 사항 · 증빙 연결 확인',text:mapping?'통화 연결 이력이 등록되었습니다. 검증을 실행하고 판정 및 거래 완료 상태를 확인하십시오.':'수사기록에 대응하는 기관 통화를 선택하고 연결을 확인하십시오. 증빙이 없는 경우 근거 부족 검증을 진행할 수 있습니다.',target:'verification',action:'검증 화면으로'}:tab==='verification'?{title:verification?'다음 절차 · 관리자 검토':'처리 사항 · 검증 실행',text:verification?'검증 결과 및 기록 상태 확인 후 관리자 검토가 필요합니다. 불일치·근거 부족·입력 변경 항목이 있으면 보완 후 재검증하십시오.':'등록 원문과 구조화 결과를 확인한 후 검증을 실행하십시오. 상태가 불명확한 요청은 재제출하지 말고 기존 요청을 조회하십시오.',target:verification?'admin':null,action:'관리자 검토 화면으로'}:null;

 async function register(revision=false){const c=await api<Claim>('/api/v1/cases/'+id+'/claims',{claim_text:text,step_id:stepId,...(revision&&latest?{claim_id:latest.claim_id}:{})});setSelectedClaim(c.claim_id+':'+c.claim_version);setMessage(isMockMode()?`원문 v${c.claim_version} 가상 원문 기록 완료`:`원문 v${c.claim_version} 원문 고정 확인 완료`);verifyKey.current=null;setDraft(null)}
 return <><Link to="/workspace" className="back"><ArrowLeft size={14}/> 사건 목록</Link><div className="page-title"><div><span className="eyebrow">CASE WORKSPACE / 가상 통화 검증</span><h1>{item.title}</h1><p className="muted mono">{item.case_id}</p></div><button disabled={disabled} onClick={()=>void run('새로고침',refresh)}><RefreshCw size={16}/>상태 새로고침</button></div>

 {!isMockMode()&&tab==='verification'&&requestRows.size>0&&<Panel title="검증 요청 처리 상태" side={<span className="caption">판정과 거래 완료는 별도 확인</span>}>{[...requestRows.values()].reverse().map(job=><div className="request-row" key={job.verification_id}><div className="actions"><Badge value={job.request_state}/><strong>{label(job.phase)}</strong></div><Hash value={job.verification_id}/>{job.tx_hash&&<Hash value={job.tx_hash}/>}<p className="caption">{job.request_state==='CONFIRMED'?'서버에서 거래 완료를 확인했습니다. 판정 내용은 검증 화면에서 확인하세요.':job.request_state==='UNKNOWN'?'재제출하지 않고 기존 요청을 조회합니다.':'화면을 새로고침해도 서버에 저장된 요청을 조회할 수 있습니다.'}</p>{job.error&&<Notice error>{job.error}</Notice>}<button disabled={disabled} onClick={()=>void run('기존 검증 요청 상태 조회',async()=>{const fresh=await api<VerificationRequest>('/api/v1/verification-requests/'+encodeURIComponent(job.verification_id));await waitForVerification(api,fresh);setMessage('기존 검증 요청의 완료를 확인했습니다.')})}>기존 요청 상태 조회</button></div>)}</Panel>}
 {busy&&<div className="working" role="status"><LoaderCircle className="spin" size={18}/><div>{busy} 중입니다. 저장 확정 여부를 기다려 주세요.</div></div>}{error&&<Notice error>{error}</Notice>}{message&&<Done>{message}</Done>}
 <div className="actions spaced"><button disabled={disabled} aria-current={tab==='overview'?'page':undefined} onClick={()=>go('overview')}>사건 개요</button><button disabled={disabled} aria-current={tab==='history'?'page':undefined} onClick={()=>go('history')}>검증 이력 조회</button></div>
 <nav className="flow-steps workflow-stages" aria-label="사건 업무 단계">{tabs.map(([value,name],i)=><button key={value} className={steps[i]==='완료'?'complete':''} aria-current={tab===value?'step':undefined} disabled={disabled} onClick={()=>go(value)}><span>{i+1}</span><strong>{name}</strong><small>{tab===value?'현재 · ':''}{steps[i]}</small></button>)}</nav>
 <div className="case-step-select"><Badge value={item.status}/>{(item.steps?.length ?? 0)>1&&<label>수사 단계 <select aria-label="수사 단계" value={stepId} disabled={disabled} onChange={e=>{setStepId(Number(e.target.value));setSelectedClaim('');setSelectedProof('');setDraft(null)}}>{(item.steps?.length?item.steps:[{step_id:0,step_name:'통화 사실 확인'}]).map(x=><option key={x.step_id} value={x.step_id}>{x.step_id+1}. {x.step_name}</option>)}</select></label>}</div>
 {tab==='overview'&&<><div className="case-summary"><div><span>현재 상태</span><Badge value={item.status}/></div><div><span>수사 기록</span><strong>{item.claims.length}건</strong></div><div><span>기관 증빙</span><strong>{item.proofs.length}건</strong></div><div><span>최근 검증</span>{verification?<Badge value={verification.verdict||verification.processing_status}/>:<span>검증 전</span>}</div></div><EvidenceDeadlines key={item.case_id} caseId={item.case_id} canEdit={canOfficer}/><WorkflowCheck item={item} role={role} system={system} verification={verification} hasProof={hasProof}/><div className="task-grid">{tabs.map(([value,name],i)=><button className="task-card" key={value} onClick={()=>go(value)}><span className="task-number">0{i+1}</span><strong>{name}</strong><small>{steps[i]}</small><p>{({records:'수행한 수사행위를 원문으로 등록합니다.',structure:'등록 원문의 대상·행위·시각·결과를 추출합니다.',proofs:'원천기관 제출 증빙에 전자서명합니다.',mapping:'수사기록에 대응하는 통화 증빙을 지정합니다.',verification:'수사기록과 증빙의 대조 결과를 기록합니다.',admin:'검증 결과를 검토하고 승인합니다.',close:'종결 요건을 확인하고 사건을 종결합니다.'} as Record<string,string>)[value]}</p><ArrowRight size={18}/></button>)}</div></>}
 {tab!=='overview'&&<details className="spaced"><summary>서명 방식 상세</summary><p>기관 증빙은 EIP-712 전자서명으로, 증빙 연결·승인·종결은 메시지 서명으로 처리합니다.</p></details>}

 <div className="tab-content"><div>
 <div hidden={tab!=='records'}><Panel title="01 · 수사기록 원문 등록" side={<Badge value={claim?.chain_status||'PENDING'}/>}>
 {!isMockMode()&&canOfficer&&<details><summary>수사 단계 추가</summary><label>단계 이름<input className="team-input" aria-label="새 수사 단계" value={newStepName} onChange={e=>setNewStepName(e.target.value)}/></label><button disabled={disabled||!newStepName.trim()} onClick={()=>void run('수사 단계 추가',async()=>{await api('/api/v1/cases/'+id+'/steps',{step_name:newStepName,is_required:true});setNewStepName('');setMessage('수사 단계를 추가했습니다. 상단에서 단계를 선택하세요.')})}>필수 수사 단계 추가</button></details>}<label>수사 진행 기록<textarea className="team-input" aria-label="수사 진행 기록" rows={4} value={text} onChange={e=>setText(e.target.value)} placeholder="수행한 수사행위를 건별로 입력하십시오."/></label>
 <div className="actions"><button className="primary" disabled={disabled||!canOfficer||!text.trim()||!!latest} onClick={()=>void run('수사기록 원문 고정',()=>register())}><LockKeyhole size={16}/>원문 등록 및 고정</button><button disabled={disabled||!canOfficer||!latest||!text.trim()} onClick={()=>void run('Claim 새 버전 고정',()=>register(true))}>새 버전으로 등록</button>{latest&&<button disabled={disabled} onClick={()=>setText(latest.claim_text)}>등록 원문 불러오기</button>}</div>
 <p className="caption">{isMockMode()?'가상 기록을 브라우저에 저장합니다. 실제 원문 고정 거래는 없습니다. ':''}앞뒤 공백과 줄바꿈을 포함한 원문 그대로 SHA-256을 계산합니다. 수정하면 새 버전으로 기록합니다.</p>
 {claim&&<><div className="version-select"><label>등록된 원문 버전<select aria-label="원문 버전" value={claim.claim_id+':'+claim.claim_version} onChange={e=>{setSelectedClaim(e.target.value);setSelectedProof('');verifyKey.current=null}}>{stepClaims.map(c=><option key={c.claim_id+':'+c.claim_version} value={c.claim_id+':'+c.claim_version}>v{c.claim_version} · {short(c.claim_id)}</option>)}</select></label><span className="muted">{current?'최신 등록 원문':'이전 원문 · 읽기 전용'}</span></div><blockquote>{claim.claim_text}</blockquote><dl className="fields"><div><dt>원문 해시</dt><dd><Hash value={claim.claim_hash}/></dd></div><div><dt>거래 해시</dt><dd><Hash value={claim.claim_tx_hash}/></dd></div><div><dt>등록 시각</dt><dd>{fmt(claim.claim_created_at)} · 한국시간</dd></div></dl></>}
 </Panel></div>
 <div hidden={tab!=='structure'}><Panel title="02 · AI 구조화 확인" side={<Badge value={extraction?.extraction_status||'PENDING'}/>}>
 <Notice>{system?.ai.is_simulated?isMockMode()?'미리 정의한 프론트엔드 가상 추출 결과입니다. 실제 AI·서버 모듈을 실행하지 않습니다.':'명시적으로 켠 고정 추출 응답입니다. 외부 Gemini 호출은 없습니다. 판정·서명·체인은 실제 코드를 실행합니다.':'등록 원문에서 대상·행위·시각·결과를 추출합니다. 검증 결과는 증빙 대조 후 별도로 산출됩니다.'}</Notice>
 <button className="primary" disabled={disabled||!canOfficer||!claim||!current} onClick={()=>void run('AI 추출',async()=>{const r=await api<{execution:{is_simulated:boolean}}>('/api/v1/claims/'+claim!.claim_id+'/extract',{claim_version:claim!.claim_version});verifyKey.current=null;setMessage(r.execution.is_simulated?'고정 응답 추출 완료 · 외부 AI 호출 없음':'구조화 응답 수신 · 처리 결과를 확인하십시오.')})}>구조화 실행</button>
 {extraction?<><div className="mini-fields extraction-fields">{extraction.actions.map((a,i)=><div className="extracted" key={i}>
  <p>행동 <strong>{a.action_type ? label(a.action_type) : '미기재'}</strong></p>
  <p>기록상 결과 <strong>{a.action_result ? label(a.action_result) : '미기재'}</strong></p>
  <p className="caption">수사기록에서 추출 · 증빙 검증 전</p>
  <p>날짜 {a.occurred_date ?? '미기재'}</p>
  <p>시각 (한국시간) {a.occurred_time ?? '미기재'}</p>
  {a.occurred_date===undefined&&a.occurred_time===undefined&&a.occurred_at&&<p className="caption">기존 추출 시각 {fmt(a.occurred_at)} · 한국시간</p>}
  <p>대상 ID {a.target_id || '미기재'}</p>
  <p>원문 근거</p><blockquote>{a.source_excerpt || '미기재'}</blockquote>
 </div>)}</div><p className="caption">모델: {system?.ai.is_simulated?'고정 응답 (모델 실행 없음)':extraction.model_name} · 프롬프트 {extraction.prompt_version}</p>{extraction.review_required&&<Notice>행동 수·누락 정보를 확인하세요. 여러 행동이면 원문을 보존하고 행동별 새 원문으로 분리해야 합니다.</Notice>}</>:<Empty>원문 등록 후 구조화를 실행하십시오.</Empty>}
 </Panel></div>
 <div hidden={tab!=='proofs'}><Panel title="03 · 기관 증빙 제출·서명" side={<span className="demo-label demo-disclosure">가상 통신사</span>}>
 <p>기관 담당자는 제출하는 통화 증빙에 서명합니다.</p>
 {item.case_id.startsWith('FP-minji-')&&<label>통화 내역<select aria-label="통화 내역" value={presentationCall} disabled={disabled||!canAgency} onChange={e=>{setPresentationCall(e.target.value);setDraft(null)}}><option value="first">1차 · 23:05 · 미응답</option><option value="second">2차 · 23:12 · 연결 성공</option></select></label>}
 <div className="actions spaced"><button disabled={disabled||!canAgency||item.scenario_id==='insufficient'} onClick={()=>void run('기관 서명 초안 생성',async()=>{setDraft(await api<Draft>('/api/v1/proofs/drafts',{case_id:id,step_id:stepId,presentation_call:presentationCall}));setMessage('증빙 내용·해시 확정 · MetaMask 서명 대기')})}>{item.case_id.startsWith('FP-minji-')?'증빙 발급·서명 준비':'평가용 증빙 발급·서명 준비'}</button><button className="primary" disabled={disabled||!canAgency||!draft} onClick={()=>void run('MetaMask 서명 및 기록',async()=>{const signature=await signProof(draft!);await api('/api/v1/proofs/anchor',{draft_id:draft!.draft_id,signature});setDraft(null);verifyKey.current=null;setMessage(isMockMode()?'기관 제출 증빙 가상 서명 완료 · 실제 서명·거래 없음':'기관 제출 증빙 응답 수신 · 아래 기록 상태를 확인하세요.')})}>{isMockMode()?'가상 기관 서명 시연':'MetaMask 서명·저장'}</button></div>
 {role!=='AGENCY'&&<p className="caption">상단 업무 역할을 ‘원천기관’으로 바꿔 실행하세요. 입력·검증은 ‘수사 담당자’ 역할입니다.</p>}
 {item.scenario_id==='insufficient'&&<Notice>기관 증빙 미확보 사례입니다. 증빙 연결 없이 자동 검증을 실행해 근거 부족 결과를 기록할 수 있습니다.</Notice>}
 {draft&&<><p className="caption">서명 계정: <Hash value={draft.signer_address}/></p><Notice>{draft.domain_warning}</Notice><details><summary>전자서명 대상 데이터 확인</summary><pre className="json-view">{JSON.stringify(draft.typed_data,null,2)}</pre></details></>}
 <p className="caption">{isMockMode()?'Mock 모드에는 지갑 설치가 필요하지 않습니다. ':''}MetaMask가 없다면 <a className="text-link" href="https://metamask.io/download" target="_blank" rel="noreferrer">공식 설치 페이지</a>에서 설치하세요. 로컬 테스트 계정만 사용하며 실제 자금은 필요하지 않습니다.</p>
 </Panel></div>
 <div hidden={tab!=='mapping'}><Panel title="04 · 증빙 연결" side={<span className="muted">{item.proofs.length}개 후보</span>}>
 {!item.proofs.length?<Empty>기관 제출 증빙이 없습니다.</Empty>:<><div className="table-wrap"><table><thead><tr><th>선택</th><th>통화 ID·시각</th><th>기관 원본 결과</th><th>기록 상태</th></tr></thead><tbody>{item.proofs.filter(p=>p.step_id===stepId).map(p=><tr className={proof?.proof_id===p.proof_id?'selected-row':''} key={p.proof_id}><td><input type="radio" name="proof" aria-label={'통화 후보 '+p.call_id} checked={proof?.proof_id===p.proof_id} onChange={()=>{setSelectedProof(p.proof_id);verifyKey.current=null}}/></td><td>{p.call_id}<p>{fmt(p.proof_occurred_at)}</p></td><td><Badge value={p.result}/></td><td><Badge value={p.chain_status}/>{canAgency&&!isRecorded(p.chain_status)&&<button className="small-button" disabled={disabled} onClick={()=>void run('선택 Proof 서명 준비',async()=>setDraft(await api<Draft>('/api/v1/proofs/drafts',{case_id:id,step_id:stepId,proof_id:p.proof_id,proof_version:p.proof_version})))}>서명 준비</button>}</td></tr>)}</tbody></table></div><button disabled={disabled||!canOfficer||!current||!claim||!proof||!isRecorded(proof.chain_status)} className="primary spaced" onClick={()=>void run('증빙 연결 확인',async()=>{await api('/api/v1/claims/'+claim!.claim_id+'/proof-mappings',{claim_version:claim!.claim_version,proof_id:proof!.proof_id,proof_version:proof!.proof_version});verifyKey.current=null;setMessage('증빙 연결 이력이 등록되었습니다. 검증은 별도로 실행하여야 합니다.')})}>선택한 통화와 연결 확인</button></>}
 {mapping&&<p className="caption">연결 확인: {mapping.evidence_note} · {fmt(mapping.confirmed_at)}</p>}
 </Panel></div>
 </div><aside className="workflow-side">
 <div hidden={tab!=='verification'}><Panel title="수사기록·기관 증빙 대조"><div className="compare-grid source-compare"><article><span className="eyebrow">수사기록 원문</span><blockquote>{claim?.claim_text||'수사기록을 선택하십시오.'}</blockquote></article><article><span className="eyebrow">기관 제출 증빙</span><p>{proof?proof.issuer_agency_id+' · '+proof.call_id:'선택한 증빙 없음'}</p><details><summary>증빙 원본 보기</summary><pre className="json-view">{proof?.source_bytes||'증빙이 없습니다. 근거 부족으로 검증할 수 있습니다.'}</pre></details></article></div><div className="comparison-head"><span>담당자 주장</span><ArrowRight size={17}/><span>원천기관 증빙</span></div>
 {action?<div className="compare-fields">{[['행동',label(action.action_type),proof?label(proof.action_type):'증빙 미선택'],['대상',action.target_id||'미확인',proof?.target_id||'미확인'],['발생 시각',fmt(action.occurred_at),fmt(proof?.proof_occurred_at)],['통화 결과',label(action.action_result==='SUCCESS'?'CALL_CONNECTED':action.action_result==='FAIL'?'CALL_FAILED':action.action_result),proof?label(proof.result):'미확인']].map(([n,a,b])=><div key={n}><span>{n} <span className={'field-check '+(!proof?'amber':a===b?'green':'red')}>{!proof?'비교 대기':a===b?'표시값 일치':'차이 확인'}</span></span><p>{a}</p><p>{b}</p></div>)}</div>:<Empty>수사기록 구조화 후 대조 항목이 표시됩니다.</Empty>}
 {proof&&<><dl className="fields"><div><dt>기관</dt><dd>{proof.issuer_agency_id}</dd></div><div><dt>증빙 참조</dt><dd>{short(proof.proof_id)} · v{proof.proof_version}</dd></div><div><dt>증빙 해시</dt><dd><Hash value={proof.proof_hash}/></dd></div><div><dt>원본 해시</dt><dd><Hash value={proof.source_sha256}/></dd></div></dl><details><summary>가상 기관 원본 확인</summary><pre className="json-view">{proof.source_bytes}</pre></details></>}
 <p className="caption">{isMockMode()?'가상 자료를 대조한 시연 결과입니다.':'자동 검증은 제출 증빙의 서명과 연결 근거를 함께 확인합니다.'} 시각은 한국시간으로 표시합니다.</p>
 </Panel></div>
 <div hidden={tab!=='verification'}><Panel title={isMockMode()?'05 · 가상 검증 결과':'05 · 자동 검증'}>

 <button className="primary full-width" disabled={disabled||!canOfficer||!claim||!extraction||!current} onClick={()=>void run('검증 및 판정 기록',async()=>{verifyKey.current ||= randomUUID();await api('/api/v1/verifications',{claim_id:claim!.claim_id,claim_version:claim!.claim_version,request_id:verifyKey.current});setMessage(isMockMode()?'가상 판정 기록 완료 · 실제 AI·블록체인 실행 없음':'검증 응답 수신 · 판정 및 기록 상태를 확인하십시오.')})}>검증 실행 및 판정 기록</button>
 {verification?<><button className="spaced" disabled={disabled||isMockMode()} onClick={()=>void run('서버 판정 결과 조회',async()=>setServerResult(await api<Verification>('/api/v1/verifications/'+verification.verification_id)))}>자동 대조 결과 다시 조회</button>{serverResult&&<Notice>서버 조회: {serverResult.processing_status} · {serverResult.verdict||'최종 판정 없음'}<Hash value={serverResult.verification_tx_hash}/></Notice>}<div className="verdict-card"><Badge value={verification.verdict||verification.processing_status}/><p>{verification.reason_text}</p><div className="actions"><Badge value={verification.freshness_status}/><Badge value={verification.chain_status}/></div></div>{verification.conflicts.map((c,i)=><Notice error key={i}>{c.field}: {c.claim_value||'미확인'} ↔ {c.proof_value||'미확인'} ({c.reason_code})</Notice>)}{verification.missing_information.length>0&&<Notice>추가 확인: {verification.missing_information.join(', ')}</Notice>}<p className="caption">입력 원문 v{verification.claim_ref.claim_version} · 정책 {verification.decision_policy_version}</p><Hash value={verification.verification_hash}/><button className="spaced" disabled={disabled} onClick={()=>void run('거래 상태 조회',async()=>{setTx(await api<Transaction>('/api/v1/blockchain/transactions/'+verification.request_id))})}>거래 상태 다시 조회</button>{tx&&<div className="spaced"><Badge value={tx.chain_status}/><Hash value={tx.tx_hash}/></div>}<IntegrityPanel id={verification.verification_id}/></>:<Empty>검증 전입니다. 기관 제출 증빙이 없으면 근거 부족으로 기록할 수 있습니다.</Empty>}
 </Panel></div>
 {(tab==='admin'||tab==='close')&&(
  !verification||verification.verdict!=='SUPPORTED'||!fresh||!latest
  ||verification.claim_ref.claim_id!==latest.claim_id
  ||verification.claim_ref.claim_version!==latest.claim_version
  ||(!isMockMode()&&verification.chain_status!=='CONFIRMED')
  ? <Notice error>관리자 단계로 진행할 수 없습니다. 최신 수사기록과 기관 증빙을 보완하고 자동 검증에서 증빙 일치 및 기록 완료를 확인해 주세요.</Notice>
  : <VerifiedAdminStage key={tab+':'+verification.verification_id} verificationId={verification.verification_id}>
     <AdminReview section={tab} item={{...item,verifications:item.verifications.filter(v=>v.step_id===stepId)}} system={system} role={role} onChange={refresh}/>
    </VerifiedAdminStage>
 )}
 {tab==='admin'&&<ProcedureNote title="다음 업무 · 사건 종결">관리자 승인과 사건 종결 조건을 확인해 주세요.<button disabled={disabled} onClick={()=>go('close')}>종결 화면으로<ArrowRight size={14}/></button></ProcedureNote>}
 <div hidden={tab!=='history'}><button disabled={disabled} onClick={()=>void run('기록 개수 조회',async()=>setChainCounts(await api<Record<string,unknown>>('/api/v1/cases/'+id+'/chain-status')))}><Database size={16}/>{isMockMode()?'가상 기록 개수 확인':'블록체인 이력 개수 확인'}</button>{chainCounts&&<pre className="json-view">{JSON.stringify(chainCounts,null,2)}</pre>}</div>
 </aside></div>
 <div hidden={tab!=='history'}><Panel title="수사·검증 진행 이력">{(item.reviews?.length||0)>0&&<div className="review-history"><h3>전체 관리자 확인 이력 · 이전 판정 포함</h3>{item.reviews!.map(r=><div className="review-row" key={r.review_id}><Badge value={r.review_status}/><p>{r.reason_text}</p><small>검증 {short(r.verification_id)} · {fmt(r.reviewed_at)}</small><Badge value={r.chain_status}/></div>)}</div>}{!item.claims.length?<Empty>등록된 이력이 없습니다.</Empty>:<ol className="audit-timeline">{item.claims.map(c=><li key={c.claim_id+':'+c.claim_version}><span>원문 v{c.claim_version} 고정</span><small>{fmt(c.claim_created_at)}</small><p>{c.claim_text}</p><Badge value={c.chain_status}/></li>)}{item.verifications.map(v=><li key={v.verification_id}><span>자동 대조 결과 · 원문 v{v.claim_ref.claim_version}</span><small>{fmt(v.created_at)}</small><p>{v.reason_text}</p><Badge value={v.verdict||v.processing_status}/> <Badge value={v.freshness_status}/></li>)}</ol>}</Panel></div>
 {procedure&&<ProcedureNote title={procedure.title}>{procedure.text}{procedure.target&&<button disabled={disabled} onClick={()=>go(procedure.target!)}>{procedure.action}<ArrowRight size={14}/></button>}</ProcedureNote>}
 </>
}

function HistoryPage(){
 const [cases,setCases]=useState<Case[]>([]),[selected,setSelected]=useState<Verification|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[transaction,setTransaction]=useState<Transaction|null>(null),[integrity,setIntegrity]=useState<{verification_hash_matches:boolean;claim_hash_matches:boolean;onchain_matches:boolean;scope:string}|null>(null),[transactions,setTransactions]=useState<Transaction[]>([]);
 async function refresh(){setLoading(true);try{setCases(await api<Case[]>('/api/v1/cases'));setTransactions(await api<Transaction[]>('/api/v1/blockchain/transactions'));setError('')}catch(e){setError(errorText(e))}finally{setLoading(false)}}
 useEffect(()=>{void refresh()},[]);
 const rows=cases.flatMap(c=>c.verifications).sort((a,b)=>(b.created_at||'').localeCompare(a.created_at||''));
 return <><div className="page-title"><div><span className="eyebrow">AUDIT TRAIL</span><h1>{isMockMode()?'검증·가상 처리 이력':'검증·블록체인 이력'}</h1><p className="muted">{isMockMode()?'가상 판정과 관리자 처리 이력입니다. 실제 블록체인 기록은 없습니다.':'백엔드에 보관된 판정과 로컬 체인의 실제 거래를 조회합니다.'}</p></div><button onClick={()=>void refresh()}><RefreshCw size={16}/>새로고침</button></div>{error&&<Notice error>{error}</Notice>}
 <section className="panel"><div className="panel-heading"><h2>판정 기록</h2><span className="muted">{rows.length}건</span></div>{loading?<Loading/>:!rows.length?<Empty>검증 기록이 없습니다.</Empty>:<div className="table-wrap"><table><thead><tr><th>검증 ID</th><th>판정·최신성</th><th>기록 시각</th><th>블록체인 상태</th><th>상세</th></tr></thead><tbody>{rows.map(v=><tr key={v.verification_id}><td>{short(v.verification_id)}<p>원문 v{v.claim_ref.claim_version}</p></td><td><Badge value={v.verdict||v.processing_status}/><p><Badge value={v.freshness_status}/></p></td><td>{fmt(v.created_at)}</td><td><Badge value={v.chain_status}/></td><td><button onClick={()=>{setSelected(v);setTransaction(null);setIntegrity(null)}}>상세 보기</button></td></tr>)}</tbody></table></div>}</section>
 {selected&&<Panel title="검증 기록 상세" side={<Link className="text-link" to={'/cases/'+selected.case_id}>사건 열기 <ArrowRight size={14}/></Link>}><div className="actions"><Badge value={selected.verdict||selected.processing_status}/><Badge value={selected.chain_status}/></div><p className="spaced">{selected.reason_text}</p><dl className="fields"><div><dt>거래 해시</dt><dd><Hash value={selected.verification_tx_hash}/></dd></div><div><dt>검증 해시</dt><dd><Hash value={selected.verification_hash}/></dd></div><div><dt>정책 해시</dt><dd><Hash value={selected.policy_hash}/></dd></div><div><dt>입력 참조</dt><dd>{selected.claim_ref.claim_id} · v{selected.claim_ref.claim_version}</dd></div></dl><button onClick={()=>void api<Transaction>('/api/v1/blockchain/transactions/'+selected.request_id).then(setTransaction).catch(e=>setError(errorText(e)))}>{isMockMode()?'가상 기록 상태 조회':'실제 거래 상태 조회'}</button>{transaction&&<p className="spaced"><Badge value={transaction.chain_status}/></p>}<IntegrityPanel id={selected.verification_id}/><details><summary>원본 응답 보기</summary><pre className="json-view">{JSON.stringify(selected,null,2)}</pre></details></Panel>}
 <Panel title="관리자 확인·종결 이력">{cases.flatMap(c=>c.reviews||[]).length===0?<Empty>관리자 확인 이력이 없습니다.</Empty>:cases.flatMap(c=>c.reviews||[]).map(r=><div className="review-row" key={r.review_id}><Badge value={r.review_status}/><p>{r.reason_text}</p><small>{short(r.verification_id)} · {fmt(r.reviewed_at)}</small><Badge value={r.chain_status}/></div>)}{cases.filter(c=>c.status==='CLOSED').map(c=><div className="review-row" key={c.case_id}><Badge value="CLOSED"/><p>{c.title} · {c.close_reason}</p><small>{fmt(c.closed_at)}</small>{isMockMode()?<Badge value="MOCK"/>:<span className="muted">서버 종결 이력</span>}</div>)}</Panel>
 <Panel title={isMockMode()?'가상 처리 요청 이력':'거래 요청 이력 · 저장 상태'}>{!transactions.length?<Empty>거래 요청이 없습니다.</Empty>:<div className="table-wrap"><table><thead><tr><th>종류</th><th>요청 ID</th><th>저장 상태</th><th>조회</th></tr></thead><tbody>{transactions.map(t=><tr key={t.request_id}><td>{t.kind}</td><td className="mono">{short(t.request_id)}</td><td><Badge value={t.chain_status}/></td><td><button onClick={()=>void api<Transaction>('/api/v1/blockchain/transactions/'+t.request_id).then(v=>{setTransaction(v);setTransactions(prev=>prev.map(p=>p.request_id===v.request_id?v:p))}).catch(e=>setError(errorText(e)))}>상태 조회</button></td></tr>)}</tbody></table></div>}{transaction&&<div className="spaced"><Badge value={transaction.chain_status}/><Hash value={transaction.tx_hash}/></div>}</Panel><Notice>{isMockMode()?'Mock 데이터는 이 브라우저에 저장됩니다. 실제 블록체인 기록은 없으며 시연 도구에서 초기화할 수 있습니다. ':''}Hardhat 체인을 새로 시작하면 이전 실행의 거래는 현재 체인에 존재하지 않을 수 있습니다. 이 버전은 배포 블록별로 시연 데이터를 분리합니다.</Notice></>
}
