import {useEffect,useState} from 'react';
import {teamRequest,signPayload,connectLocalWallet,TeamError,type TeamCase,type Analysis,type Delivery,type SystemStatus,type Scenario} from '../api/team';
import {useLoad} from '../hooks/useLoad';
import {PageTitle,Panel,State,Badge} from '../components/UI';

const verdictLabel=(value:string|null)=>({SUPPORTED:'기록·증빙 일치',CONTRADICTED:'항목 불일치 · 확인 필요',INSUFFICIENT:'증빙 부족 · 판단 보류'}[value||'']||'분석 실패');
const fieldLabel:Record<string,string>={target_id:'대상 식별자',action_type:'수사행위',claimed_time:'행위 시각',status_claim:'행위 결과'};
const valueText=(value:unknown)=>value==null?'정보 없음':typeof value==='object'?JSON.stringify(value):String(value);
const statusLabel:Record<string,string>={MATCH:'일치',MISMATCH:'불일치',UNKNOWN:'확인 불가',NOT_APPLICABLE:'비교 제외'};

export default function TeamIntegration(){
  const cases=useLoad(()=>teamRequest<TeamCase[]>('/cases'),'team');
  const system=useLoad(()=>teamRequest<SystemStatus>('/system/status'),'system');
  const scenarios=useLoad(()=>teamRequest<{scenarios:Scenario[]}>('/demo/scenarios'),'scenarios');
  const [cid,setCid]=useState(''),[step,setStep]=useState(0);
  const [text,setText]=useState('2026년 10월 10일 14시에 P001에게 전화했으나 연결 실패.');
  const [proof,setProof]=useState(JSON.stringify({proof_id:'DEMO-P1',proof_version:1,action_type:'PHONE_CALL',target_id:'P001',occurred_at:'2026-10-10T14:00:00+09:00',action_result:'FAIL',proof_text:'P001에게 발신했으나 무응답으로 연결되지 않음.'},null,2));
  const [analysis,setAnalysis]=useState<Analysis>(),[delivery,setDelivery]=useState<Delivery>();
  const [agency,setAgency]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [history,setHistory]=useState<Analysis[]>([]),[requestId,setRequestId]=useState(()=>crypto.randomUUID());
  const [notice,setNotice]=useState('');
  const selected=cases.data?.find(c=>c.case_id===cid);
  useEffect(()=>{if(system.data?.local_demo?.agency_address)setAgency(system.data.local_demo.agency_address)},[system.data?.local_demo?.agency_address]);

  async function perform(fn:()=>Promise<void>){
    setBusy(true);setError('');setNotice('');
    try{await fn()}catch(e){setError(e instanceof TeamError?e.message+(typeof e.detail==='object'?' '+JSON.stringify(e.detail):''):e instanceof Error?e.message:String(e))}
    finally{setBusy(false)}
  }
  function changed(){setAnalysis(undefined);setDelivery(undefined);setError('');setNotice('');setRequestId(crypto.randomUUID())}
  async function loadHistory(caseId=cid){
    const response=await teamRequest<{history:Analysis[]}>(`/ai/cases/${encodeURIComponent(caseId)}/history`);
    setHistory(response.history);
  }
  function chooseScenario(scenario:Scenario){
    setCid(scenario.case_id);setStep(scenario.step_id);setText(scenario.raw_claim_text);
    setProof(scenario.proof?JSON.stringify(scenario.proof,null,2):'');setHistory([]);changed();
  }
  async function analyze(draft:boolean){await perform(async()=>{
    const parsed=proof.trim()?JSON.parse(proof):null;
    const response=await teamRequest<{analysis:Analysis}>(draft?'/ai/drafts':'/ai/analyses',{
      request_id:requestId,case_id:cid,step_id:step,claim_id:`${cid}:${step}`,
      claim_version:1,raw_claim_text:text,proof:parsed,evidence:[]
    });
    setAnalysis(response.analysis);setDelivery(undefined);await loadHistory();
  })}
  async function poll(){
    if(!analysis)return;
    const state=await teamRequest<Delivery>(`/ai/anchor-status/${analysis.analysis_id}`);
    setDelivery(state);if(state.anchor_status==='CONFIRMED')cases.retry();
  }
  async function anchor(){await perform(async()=>{
    if(!analysis)return;
    const parsed=JSON.parse(proof);
    const occurred=Date.parse(parsed.occurred_at);
    if(!Number.isFinite(occurred)||!/([+-]\d\d:\d\d|Z)$/.test(parsed.occurred_at))throw new Error('Proof 시각에 시간대가 필요합니다.');
    if(!/^0x[0-9a-fA-F]{40}$/.test(agency))throw new Error('등록된 시연용 기관 주소를 입력해 주세요.');
    const agencyState=await teamRequest<{nonce:string;signer:string}>(`/blockchain/agencies/${agency}`);
    if(!Number.isSafeInteger(Number(agencyState.nonce)))throw new Error('nonce가 프론트엔드 안전 정수 범위를 초과했습니다.');
    const body={analysis_id:analysis.analysis_id,agency,nonce:Number(agencyState.nonce),deadline:Math.floor(Date.now()/1000)+600,evidence_timestamp:Math.floor(occurred/1000),signature:''};
    const payload=await teamRequest<{domain:Record<string,unknown>;types:Record<string,unknown>;message:Record<string,unknown>}>(`/ai/drafts/${analysis.analysis_id}/signing-payload`,body);
    body.signature=await signPayload(payload,agency,agencyState.signer);
    setDelivery({anchor_status:'UNKNOWN'});
    try {
      setDelivery(await teamRequest<Delivery>('/ai/anchor',body));cases.retry();await loadHistory();
    } catch(e){
      // A lost response may follow a successful broadcast. Query, don't resend.
      try{await poll()}catch{/* Preserve UNKNOWN until the user can query. */}
      throw e;
    }
  })}
  const aiReady=system.data?.ai_ready??true;
  const analysisAllowed=!busy&&!!selected&&!selected.is_closed&&!!selected.steps.length&&aiReady;
  const frozen=['CONFIRMED','SUBMITTED','UNKNOWN','STALE_CHAIN'].includes(delivery?.anchor_status||'');
  const checks=analysis?.action_results.flatMap(action=>action.field_checks||[])||[];

  return <>
    <PageTitle eyebrow="CONNECTED WORKSPACE" title="AI·블록체인 연결 워크스페이스" description="사건 조회부터 기록 비교, 기관 서명, 체인 영수증과 이력 확인까지 진행합니다."/>
    <div className="scope-note">
      모든 사건과 기관은 가상입니다. {system.data?.execution.label||'연결 상태 확인 중'}.
      블록체인 기록은 서명된 내용의 보존을 확인하며, 원문 사실의 진실성을 보증하지 않습니다.
    </div>
    <Panel title="연결 상태">
      <div className="pane-body">
        <State loading={system.loading} error={system.error} retry={system.retry}/>
        {system.data&&<>
          <div className="connection-grid">
            <div><span>백엔드</span><strong>연결됨</strong><small>FastAPI · SQLite</small></div>
            <div><span>분석 실행 방식</span><strong>{system.data.execution.is_simulated?'고정 응답 시연':'Gemini API'}</strong><small>{system.data.execution.is_simulated?'실제 AI 호출 없음':system.data.gemini_key_configured?`키 설정됨 · ${system.data.model}`:'Gemini 키 설정 필요'}</small></div>
            <div><span>블록체인</span><strong>{system.data.chain.ready?(system.data.chain.chain_id===31337?'로컬 체인 연결됨':'체인 연결됨'):'체인 준비 필요'}</strong><small>{system.data.chain.ready?`Chain ${system.data.chain.chain_id} · Block ${system.data.chain.block_number}`:'py start_fullproof.py 로 시작해 주세요'}</small></div>
          </div>
          <p className="mono break-all caption">컨트랙트: {system.data.chain.contract_address||'미설정'}</p>
          {!system.data.ai_ready&&<p role="alert">실제 AI 호출에는 키가 필요합니다. 프로젝트 폴더에서 <code>py configure_ai.py</code> 실행 후 서버를 재시작해 주세요.</p>}
        </>}
        <div className="actions">
          <button disabled={busy} onClick={system.retry}>연결 상태 새로고침</button>
          <button disabled={busy||!system.data?.chain.ready||system.data.environment!=='LOCAL_DEMO'} onClick={()=>perform(async()=>{await teamRequest('/demo/bootstrap',{});cases.retry();system.retry();setNotice('로컬 체인과 SQLite에 가상 사건 4건을 준비했습니다.')})}>시연 사건 준비</button>
        </div>
      </div>
    </Panel>
    <Panel title="1. 사건과 수사 기록 선택">
      <div className="pane-body">
        <State {...cases} empty={!cases.loading&&!cases.error&&!cases.data?.length}/>
        <div className="actions">
          <select aria-label="팀 사건" value={cid} disabled={busy} onChange={e=>{setCid(e.target.value);setStep(0);changed();setHistory([])}}>
            <option value="">사건을 선택해 주세요</option>
            {cases.data?.map(c=><option key={c.case_id} value={c.case_id}>{c.case_id} · {c.title}</option>)}
          </select>
          <select aria-label="팀 수사 단계" value={step} disabled={busy} onChange={e=>{setStep(Number(e.target.value));changed()}}>
            {selected?.steps.map(s=><option key={s.step_id} value={s.step_id}>{s.step_id} · {s.step_name} · {s.status||'PENDING'}</option>)}
          </select>
          <button disabled={busy} onClick={cases.retry}>사건 다시 조회</button>
        </div>
        <div className="scenario-grid" aria-label="가상 시연 시나리오">
          {scenarios.data?.scenarios.map(s=><button key={s.id} aria-label={s.label} disabled={busy||!cases.data?.some(c=>c.case_id===s.case_id)} onClick={()=>chooseScenario(s)}><strong>{s.label}</strong><small>{s.case_id}</small></button>)}
        </div>
        <p className="caption">시나리오를 누르면 해당 사건·단계·가상 기록을 불러옵니다. 고정 응답 모드는 이 네 자료만 지원합니다.</p>
      </div>
    </Panel>
    <Panel title="2. Claim · Proof 비교">
      <div className="pane-body">
        <div className="claim-proof-inputs">
          <label>원본 수사 기록<textarea aria-label="수사 기록 원문" className="team-input" rows={10} value={text} disabled={busy} onChange={e=>{setText(e.target.value);changed()}}/></label>
          <label>원천기관 Proof JSON<textarea aria-label="Proof JSON" className="team-input mono" rows={10} value={proof} disabled={busy} onChange={e=>{setProof(e.target.value);changed()}}/></label>
        </div>
        <div className="actions">
          <button className="primary" disabled={!analysisAllowed} onClick={()=>analyze(true)}>기관 서명용 분석 초안 생성</button>
          <button disabled={!analysisAllowed} onClick={()=>analyze(false)}>일반 분석 실행</button>
        </div>
        <p className="caption">일반 분석은 독립 증빙 검증기가 연결되지 않아 근거 부족일 수 있습니다. 초안은 서명 전 비교 결과이며, 자료 제공만으로 실제 열람을 확인하지 않습니다.</p>
      </div>
    </Panel>
    <State loading={busy} error={error}/>
    {notice&&<div className="scope-note" role="status">{notice}</div>}
    {analysis&&<Panel title="분석 결과와 항목별 근거">
      <div className="pane-body">
        <div className="actions"><Badge value={analysis.is_provisional?'서명 전 초안':analysis.processing_status}/><span className="caption">{analysis.execution?.label}</span></div>
        <h3 className="mt-4">{verdictLabel(analysis.verdict)}</h3><p>{analysis.reason_text}</p>
        {analysis.error_code&&<p role="alert">오류 코드: {analysis.error_code}</p>}
        {checks.length>0&&<div className="table-scroll"><table><thead><tr><th>비교 항목</th><th>Claim</th><th>Proof</th><th>결과</th></tr></thead><tbody>{checks.map((c,index)=><tr key={`${index}-${c.field}`}><td>{fieldLabel[c.field]||c.field}</td><td>{valueText(c.claim_value)}</td><td>{valueText(c.proof_value)}</td><td>{statusLabel[c.status]||c.status}</td></tr>)}</tbody></table></div>}
        <details><summary>구조화 Claim 및 상세 분석 근거</summary><pre className="json-view">{JSON.stringify({structured_claim:analysis.structured_claim,action_results:analysis.action_results},null,2)}</pre></details>
        <p className="caption">분석 ID: {analysis.analysis_id}</p>
      </div>
    </Panel>}
    {analysis?.is_provisional&&<Panel title="3. 기관 서명 → 체인 기록 확인">
      <div className="pane-body">
        <label>시연용 기관 지갑 주소<input aria-label="기관 주소" className="team-input" placeholder="체인에 등록된 기관 주소 0x…" value={agency} disabled={busy||frozen} onChange={e=>setAgency(e.target.value)}/></label>
        <div className="actions">
          <button disabled={busy} onClick={()=>perform(async()=>{const accounts=await connectLocalWallet();setNotice(`로컬 네트워크 연결 계정: ${accounts[0]||'없음'}. 체인에 등록된 서명자 계정인지 확인해 주세요.`)})}>지갑 네트워크 연결</button>
          <button className="primary" disabled={busy||!['SUPPORTED','CONTRADICTED'].includes(analysis.verdict||'')||frozen||!system.data?.chain.ready} onClick={anchor}>MetaMask 서명 및 저장 요청</button>
          <button disabled={busy} onClick={()=>perform(poll)}>저장 상태 다시 조회</button>
        </div>
        {analysis.verdict==='INSUFFICIENT'&&<p>추가 증빙이 필요합니다. 판단 보류 결과를 기존 컨트랙트의 완료 상태로 기록하지 않습니다.</p>}
        {delivery&&<div className="mt-4" role="status"><Badge value={delivery.anchor_status}/><p className="mono break-all">{delivery.transaction_hash||'트랜잭션 없음'}</p><p>{delivery.anchor_status==='CONFIRMED'?`로컬 체인 영수증 성공 확인. 사건 저장: ${delivery.case_persistence||'상태 재확인 필요'}`:'저장 완료가 확인되지 않았습니다. 결과가 불확실하면 상태를 먼저 조회해 주세요.'}</p></div>}
        <p className="caption">서명 직전에 현재 nonce와 등록 서명자를 체인에서 자동 조회합니다. 서명자의 신원은 가상의 기관 계정입니다.</p>
      </div>
    </Panel>}
    <Panel title="4. 사건별 분석·블록체인 이력">
      <div className="pane-body">
        <button disabled={!cid||busy} onClick={()=>perform(()=>loadHistory())}>이력 조회</button>
        {history.length===0&&<p className="caption">사건 선택 후 이력을 조회해 주세요.</p>}
        {history.map(a=><div className="activity-row" key={a.analysis_id}>
          <div><strong>{verdictLabel(a.verdict)}</strong><p>{a.execution?.label} · {a.is_provisional?'서명 전 분석 초안':'일반 분석'}</p><small className="mono">{a.analysis_id}</small></div>
          <button disabled={busy} onClick={()=>perform(async()=>{
            const stored=await teamRequest<{analysis:Analysis;input:{raw_text:string;proof:unknown};delivery:Delivery|null}>(`/ai/analyses/${a.analysis_id}`);
            setStep(stored.analysis.step_id);setText(stored.input.raw_text);setProof(stored.input.proof?JSON.stringify(stored.input.proof,null,2):'');
            setAnalysis(stored.analysis);setDelivery(undefined);setRequestId(crypto.randomUUID());
            if(stored.delivery){
              setDelivery({anchor_status:'UNKNOWN'});
              setDelivery(await teamRequest<Delivery>(`/ai/anchor-status/${a.analysis_id}`));
            }
            setNotice('저장된 원문과 분석을 불러왔습니다. 현재 분석 결과에서 저장 상태를 조회할 수 있습니다.');
          })}>기록 상세 보기</button>
        </div>)}
      </div>
    </Panel>
  </>;
}
