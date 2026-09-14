// Deterministic demo rules adapted from the supplied ai_engine.py.
// No model, cryptographic issuer validation, or chain transaction is implied.
export const DEMO_TIME = '2026-09-13T19:00:00+09:00';
export const ACTIONS = { PHONE_CALL:'전화 연락', LOCATION_TRACE:'위치 조회', CCTV_CHECK:'CCTV 확보', RETENTION_CHECK:'보존기한 확인' };
export const STATUS = {
 PENDING:{label:'검증 대기',tone:'pending'}, VERIFIED:{label:'검증 일치',tone:'verified'},
 MISMATCH:{label:'기록 불일치',tone:'mismatch'}, IDENTITY_MISMATCH:{label:'대상 불일치',tone:'mismatch'},
 INSUFFICIENT:{label:'증거 미확보',tone:'pending'}, INCOMPLETE:{label:'수행 미완료',tone:'warning'},
 EXPIRING_SOON:{label:'기한 임박',tone:'warning'}, EXPIRED:{label:'기한 경과',tone:'mismatch'},
 INVALID:{label:'입력 확인 필요',tone:'warning'}
};
export const SCENARIOS = [
 {id:'normal',title:'정상 검증',desc:'Claim과 Proof가 일치하는 경우'},
 {id:'mismatch',title:'기록 불일치',desc:'완료 기록과 기관 기록이 다른 경우'},
 {id:'deadline',title:'CCTV 기한 임박',desc:'증거 확보 전 보존기한이 다가온 경우'}
];
const template = [
 ['실종자 본인 연락','통신사 통화기록','MOCK-TELECOM','PHONE_CALL','P-1872','18:32','실종자 본인에게 전화하여 안전 여부를 확인했습니다.'],
 ['최근 위치 확인','통신사 기지국 기록','MOCK-TELECOM','LOCATION_TRACE','P-1872','18:40','기지국 조회를 통해 마지막 확인 위치를 확인했습니다.'],
 ['보호자·신고자 확인','보호자 통화기록','MOCK-TELECOM','PHONE_CALL','G-5580','18:45','신고자와 통화하여 귀가 여부와 마지막 목격 정보를 확인했습니다.'],
 ['주변 CCTV 확보','관제센터 확보 기록','MOCK-CCTV','CCTV_CHECK','CAM-001','18:50','마지막 확인지 주변 CCTV 영상 3건을 확보했습니다.'],
 ['시한성 증거 잔여기한 확인','관제센터 보존정책','MOCK-CCTV','RETENTION_CHECK','CAM-001','18:55','CCTV 보존정책과 확보 상태를 확인했습니다.']
];
export function createSteps(scenario='normal') {
 if(!SCENARIOS.some(s=>s.id===scenario)) throw new Error('지원하지 않는 시나리오입니다.');
 return template.map(([name,source,issuer,action,target,time,raw],i)=>{
  const deadline=scenario==='deadline'?'2026-09-14T07:00:00+09:00':'2026-09-20T19:00:00+09:00';
  const step={id:i+1,name,source,issuer,required:true,claim:{raw,action,target,time,success:true},proof:{issuer,action,target,time,success:true,kind:'record'},deadline,acquired:true};
  if(scenario==='mismatch'&&i===0) step.proof.kind='no_record';
  if(scenario==='deadline'&&(i===3||i===4)) {step.acquired=false;if(i===3){step.proof.kind='no_response';step.claim={...step.claim,raw:'',success:false};}}
  return step;
 });
}
const minutes=t=>/^([01]\d|2[0-3]):[0-5]\d$/.test(t??'')?Number(t.slice(0,2))*60+Number(t.slice(3)):NaN;
export function verifyStep(step,now=DEMO_TIME) {
 const checks=[];
 const out=(status,reason)=>({status,reason,checks,engine:'deterministic-demo-v1',source:'browser-rules',completed:status==='VERIFIED'});
 if(!step||!step.claim||!step.proof||![1,2,3,4,5].includes(step.id)) return out('INVALID','필수 입력이 누락되었습니다.');
 const {claim:c,proof:p}=step;
 if(step.id>=4){
  const hours=(Date.parse(step.deadline)-Date.parse(now))/3600000;
  if(!Number.isFinite(hours))return out('INVALID','보존기한 형식을 확인하세요.');
  checks.push({name:'보존기한',ok:step.acquired||hours>24,detail:step.acquired?'증거 확보됨':hours<=0?'보존기한 경과':`${Math.ceil(hours)}시간 남음`});
  if(!step.acquired&&hours<=0)return out('EXPIRED','CCTV 보존기한이 지났습니다. 원천기관에 보존 여부와 대체 자료를 확인해야 합니다.');
  if(!step.acquired&&hours<=24)return out('EXPIRING_SOON',`CCTV 3건이 미확보 상태입니다. 보존기한까지 ${Math.ceil(hours)}시간 남아 우선 확보가 필요합니다.`);
 }
 if(!c.raw.trim()||!c.target.trim()||!ACTIONS[c.action]||!Number.isFinite(minutes(c.time)))return out('INVALID','수행 기록·대상자·행위·시각을 모두 입력하세요.');
 if(p.kind==='no_response')return out('INSUFFICIENT','기관 응답을 아직 확보하지 못했습니다. 기록 부존재와 구분하여 재요청해야 합니다.');
 checks.push({name:'기관 기록',ok:p.kind==='record',detail:p.kind==='no_record'?'조회 기간 내 해당 발신 기록 0건':'가상 기관 기록 수신'});
 if(p.kind==='no_record')return out('MISMATCH','담당자는 연락 완료를 입력했지만, 가상 통신사의 조회 결과 해당 발신 기록이 없습니다.');
 if(p.kind!=='record')return out('INVALID','지원하지 않는 증거 형식입니다.');
 checks.push({name:'발행기관 코드',ok:p.issuer===step.issuer,detail:p.issuer});
 if(p.issuer!==step.issuer)return out('MISMATCH','해당 수사 단계에 지정된 기관과 증거의 기관 코드가 다릅니다.');
 checks.push({name:'대상자·증거 ID',ok:c.target===p.target,detail:`${c.target} / ${p.target}`});
 if(c.target!==p.target)return out('IDENTITY_MISMATCH','담당자가 입력한 대상과 기관 기록의 대상이 다릅니다. 잘못 연결된 증거인지 확인하세요.');
 checks.push({name:'행위 유형',ok:c.action===p.action,detail:`${ACTIONS[c.action]} / ${ACTIONS[p.action]??p.action}`});
 if(c.action!==p.action)return out('MISMATCH','담당자 기록과 기관 기록의 행위 유형이 다릅니다.');
 const diff=Math.abs(minutes(c.time)-minutes(p.time));
 if(!Number.isFinite(diff))return out('INVALID','기관 기록 시각을 확인하세요.');
 checks.push({name:'시각 정합성',ok:diff<=15,detail:`${diff}분 차이 · 허용 15분 이내`});
 if(diff>15)return out('MISMATCH','기록된 수행 시각이 기관 기록과 15분 넘게 차이 납니다.');
 checks.push({name:'수행 완료',ok:c.success===true&&p.success===true,detail:p.success?'기관 기록: 성공':'기관 기록: 실패'});
 if(c.success===true&&p.success!==true)return out('MISMATCH','완료로 입력했지만 기관 기록에서는 수행 성공을 확인할 수 없습니다.');
 if(c.success!==true||p.success!==true)return out('INCOMPLETE','기록의 내용이 일치하더라도 필수 행위가 완료된 것은 아닙니다.');
 if(step.id===4&&!step.acquired)return out('INCOMPLETE','CCTV 확보 기록과 실제 확보 상태를 확인해야 합니다.');
 return out('VERIFIED','대상·행위·시각·수행 완료 조건이 가상 기관 기록과 일치합니다.');
}
export function closureState(steps,results){
 const required=steps.filter(s=>s.required);
 const blockers=required.filter(s=>!results[s.id]?.completed||results[s.id]?.status!=='VERIFIED');
 return {allowed:required.length===5&&blockers.length===0,blockers};
}
export async function makeLedgerEntry(payload,previousHash=null){
 const record={...payload,previous_hash:previousHash,recorded_at:new Date().toISOString(),storage:'browser-session',on_chain:false};
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(record))))).map(b=>b.toString(16).padStart(2,'0')).join('');
 return {...record,hash};
}
