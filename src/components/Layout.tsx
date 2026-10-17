import {NavLink,Outlet,Link,useLocation} from 'react-router-dom';
import {ShieldCheck,LayoutDashboard,History,Database,ChevronRight} from 'lucide-react';
import {isMock} from '../api';
export default function Layout(){
  const team=useLocation().pathname==='/integration';
  return <div className="app-shell">
    <aside className="sidebar">
      <Link to={team?'/integration':'/'} className="brand"><div className="brand-icon"><ShieldCheck/></div><div>FullProof<small>수사행위 검증 플랫폼</small></div></Link>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="주 탐색">
        <NavLink to="/" end><LayoutDashboard size={19}/>사건 관리 · Mock</NavLink>
        <NavLink to="/history"><History size={19}/>검증 이력 · Mock</NavLink>
        <NavLink to="/integration"><Database size={19}/>AI·체인 실제 연결</NavLink>
      </nav>
      <div className="sidebar-bottom"><Database size={22}/>
        <strong>{team?'팀 API 워크스페이스':isMock?'가상 데이터 환경':'API 연동 환경'}</strong>
        <p>{team?'백엔드·분석·체인 연결 상태는 본문에서 확인합니다.':isMock?'실제 개인정보·경찰 내부 자료를 사용하지 않습니다.':'실제 API 명세와 접근 권한을 별도로 확인해야 합니다.'}</p>
        <span className="connection">{!team&&<i/>}{team?'팀 FastAPI 요청 화면':isMock?'Mock Service 활성':'HTTP Service 활성'}</span>
      </div>
    </aside>
    <div className="workspace">
      <header className="topbar"><span>FullProof <ChevronRight size={14}/> 검증 워크스페이스</span><div><span className="demo-label">{team?'TEAM API · 가상 자료':isMock?'DEMO · 시연용':'API · 연동 모드'}</span><span className="avatar">FP</span></div></header>
      <div className="demo-banner">{team?'가상 수사 자료를 팀 백엔드로 보냅니다. 분석 실행 방식과 체인 상태는 아래에서 확인하세요.':isMock?'모든 사건·Claim·Proof는 가상 데이터이며, 검증은 미리 정의한 시연용 결과입니다. 실제 AI 분석 및 블록체인 저장은 실행되지 않습니다.':'실제 API 연결 모드입니다. 응답과 권한은 팀이 합의한 API 계약을 기준으로 검토해 주세요.'}</div>
      <main><Outlet/></main><footer>FullProof © 2026 <span>독립적인 증빙으로, 확인 가능한 진행 기록</span></footer>
    </div>
  </div>;
}
