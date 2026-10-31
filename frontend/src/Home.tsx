import BrandLogo from './BrandLogo';
import {useRef,useState} from 'react';
import {ArrowRight,Building2,Info,LoaderCircle,ShieldCheck,UserRound} from 'lucide-react';
import type {Role} from './api';
import ThemeToggle from './ThemeToggle';
import {roleInfo} from './roles';

const roles:[Role,string,typeof UserRound][]=[
 ['OFFICER','수사 기록 등록 · 증빙 연결 · 검증 요청',UserRound],
 ['AGENCY','증빙 준비 · 기관 서명 · 제공 이력',Building2],
 ['ADMIN','검증 근거 검토 · 승인 · 사건 종결',ShieldCheck]
];
export default function Home({onSelect}:{onSelect:(role:Role)=>Promise<void>}){
 const [selected,setSelected]=useState<Role|null>(null),[error,setError]=useState('');
 const selecting=useRef(false);
 async function enter(role:Role){
  if(selecting.current)return;
  selecting.current=true;setSelected(role);setError('');
  try{
   if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches)await new Promise(resolve=>setTimeout(resolve,180));
   await onSelect(role);
  }catch{setError('업무 화면으로 이동하지 못했습니다. 다시 시도해 주세요.')}
  finally{selecting.current=false;setSelected(null)}
 }
 return <div className="home-shell">
  <header className="home-topbar"><a className="home-brand" href="/" aria-label="FullProof 홈"><BrandLogo/><span>수사행위 검증 플랫폼</span></a><div><span className="demo-pill">WORKSPACE</span><ThemeToggle/></div></header>
  <main className="home-main"><div className="home-heading"><span className="eyebrow">FULLPROOF WORKSPACE</span><h1 tabIndex={-1}>업무 시스템 접속</h1><p>담당 업무를 선택하여 기록·증빙·검토 업무를 진행하세요.</p></div>
   <div className="role-cards">{roles.map(([role,description,Icon],index)=><button key={role} className={'role-card role-'+role.toLowerCase()+(selected===role?' role-selected':'')} style={{animationDelay:index*65+'ms'}} disabled={selected!==null} aria-label={roleInfo[role].name+(role==='AGENCY'?'으로':'로')+' 시작'} onClick={()=>void enter(role)}>
    <div className="role-art"><img src={'/art/'+role.toLowerCase()+'.webp'} alt=""/></div>
    <div className="role-card-body"><span className="role-card-icon"><Icon size={25}/></span><h2>{roleInfo[role].name}</h2><p>{description}</p><span className="role-enter">{selected===role?<><LoaderCircle size={18} className="spin"/>업무 화면으로 이동 중</>:<>{roleInfo[role].name}{role==='AGENCY'?'으로':'로'} 시작<ArrowRight size={18}/></>}</span></div>
   </button>)}</div>
   {error&&<p role="alert" className="home-disclosure">{error}</p>}
   <p className="home-disclosure"><Info size={16}/>평가용 환경 · 사건·증빙은 예제 데이터입니다.<span>업무 선택은 로그인·권한 인증을 대신하지 않습니다.</span></p>
  </main>
  <footer className="home-footer">FullProof © 2026 <span>독립적인 증빙으로, 확인 가능한 진행 기록</span></footer>
 </div>
}
