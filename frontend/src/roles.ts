import type {Role,Case} from './api';
export const roleInfo={
 OFFICER:{name:'수사담당자',english:'INVESTIGATION',home:'사건 관리',title:'수사담당자 업무 대시보드',description:'기록을 남기고, 증빙을 연결하고, 확인할 수 있는 근거를 쌓습니다.',focus:'기록에서 검증까지',hint:'사건을 선택하면 다음 수사 업무를 이어갈 수 있습니다.'},
 AGENCY:{name:'원천기관',english:'EVIDENCE DESK',home:'증빙 제공',title:'원천기관 증빙 데스크',description:'기관이 발급한 원천 증빙을 확인하고, 서명과 제공 이력을 관리합니다.',focus:'기관 증빙의 출처를 명확하게',hint:'증빙 요청 대상 사건을 열어 증빙을 준비하거나 기존 초안을 이어서 서명하세요.'},
 ADMIN:{name:'관리자',english:'REVIEW & APPROVAL',home:'검토·승인',title:'관리자 검토 대시보드',description:'최신 검증의 근거를 살피고, 확인·보완·승인과 종결을 결정합니다.',focus:'근거를 확인한 뒤 승인',hint:'일치 판정도 관리자의 승인을 거쳐야 사건 종결 조건을 충족합니다.'}
} as const;
export const roleTabs={
 OFFICER:[['overview','사건 개요'],['records','수사 기록'],['proofs','증빙 연결'],['verification','증빙 비교·검증'],['history','검증 이력']],
 AGENCY:[['overview','제공 업무 개요'],['proofs','기관 증빙 제공'],['history','제공 이력']],
 ADMIN:[['overview','검토 개요'],['verification','검증 근거'],['admin','관리자 확인'],['history','검토 이력']]
} as const;
export const entryTab=(role:Role)=>role==='AGENCY'?'proofs':role==='ADMIN'?'verification':'overview';
export const caseLink=(role:Role,id:string)=>'/cases/'+encodeURIComponent(id)+'?tab='+entryTab(role);
export function latestVerifications(cases:Case[]){return cases.flatMap(c=>c.verifications.filter(v=>v.freshness_status==='CURRENT'&&(v.chain_status==='CONFIRMED'||v.chain_status==='MOCK')))}
