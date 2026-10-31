import {useEffect,useRef,useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {Bell,X} from 'lucide-react';
import {api,fmt} from './api';
import type {Case,Role,System} from './api';
import {mergeNotifications,notificationEvents,type NotificationState} from './notificationEvents';
export default function Notifications({role,system,disabled}:{role:Role;system:System;disabled:boolean}){
 const navigate=useNavigate(),[open,setOpen]=useState(false),[state,setState]=useState<NotificationState|null>(null),[error,setError]=useState(''),[storageError,setStorageError]=useState(false);
 const current=useRef<NotificationState|null>(null),root=useRef<HTMLDivElement>(null);
 const scope=[system.environment,system.chain.chain_id,system.chain.contract_address].join(':');
 const key='fullproof.notifications.v1:'+scope+':'+role;
 useEffect(()=>{
  let active=true,inFlight=false,timer:ReturnType<typeof setTimeout>;setOpen(false);setError('');setState(null);current.current=null;
  try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(saved&&Array.isArray(saved.known)&&Array.isArray(saved.items)){current.current=saved;setState(saved)}}catch{setStorageError(true)}
  async function poll(){
   if(!active||inFlight)return;
   inFlight=true;
   try{const cases=await api<Case[]>('/api/v1/cases');if(!active)return;const next=mergeNotifications(current.current,notificationEvents(cases,role));current.current=next;setState(next);setError('');try{localStorage.setItem(key,JSON.stringify(next))}catch{setStorageError(true)}}
   catch{if(active)setError('알림 조회가 지연되고 있습니다. 기존 알림은 유지됩니다.')}
   finally{inFlight=false;if(active){clearTimeout(timer);timer=setTimeout(()=>void poll(),15000)}}
  }
  const focus=()=>{clearTimeout(timer);void poll()};void poll();window.addEventListener('focus',focus);
  return ()=>{active=false;clearTimeout(timer);window.removeEventListener('focus',focus)};
 },[key,role]);
 useEffect(()=>{const dismiss=(e:MouseEvent)=>{if(root.current&&!root.current.contains(e.target as Node))setOpen(false)};document.addEventListener('mousedown',dismiss);return ()=>document.removeEventListener('mousedown',dismiss)},[]);
 function read(id?:string){if(!current.current)return;const next={...current.current,items:current.current.items.map(n=>!id||n.id===id?{...n,read:true}:n)};current.current=next;setState(next);try{localStorage.setItem(key,JSON.stringify(next))}catch{setStorageError(true)}}
 const unread=state?.items.filter(n=>!n.read).length||0;
 return <div className="notifications" ref={root} onKeyDown={e=>{if(e.key==='Escape'){setOpen(false);root.current?.querySelector('button')?.focus()}}}>
 <button className="notification-toggle" aria-label={'알림 · 읽지 않음 '+unread+'개'} aria-expanded={open} aria-controls="work-notifications" disabled={disabled} onClick={()=>setOpen(!open)}><Bell size={18}/>{unread>0&&<span className="notification-count">{unread>99?'99+':unread}</span>}</button>
 {open&&<section id="work-notifications" className="notification-popover" aria-label="업무 알림"><div className="notification-heading"><h2>업무 알림</h2><button aria-label="알림 닫기" onClick={()=>setOpen(false)}><X size={16}/></button></div><p className="caption">확인된 새 기록을 15초 간격으로 조회합니다.</p>{error&&<p role="status" className="caption">{error}</p>}{storageError&&<p className="caption">이 브라우저에 읽음 상태를 저장하지 못했습니다.</p>}{unread>0&&<button className="small-button" disabled={disabled} onClick={()=>read()}>모두 읽음</button>}
 {!state?.items.length?<p className="notification-empty">{role==='AGENCY'?'증빙 제공 요청 알림은 아직 지원하지 않습니다. 제공 업무 목록을 확인하세요.':state?'새 알림이 없습니다. 이전 기록은 사건 목록에서 확인하세요.':'알림을 확인하고 있습니다.'}</p>:<ul>{state.items.map(n=><li key={n.id}><button disabled={disabled} className={n.read?'notification-item read':'notification-item unread'} onClick={()=>{read(n.id);setOpen(false);navigate(n.href)}}><strong>{n.title}</strong><span>{n.case_title}</span><small>{fmt(n.at)} · {n.read?'읽음':'읽지 않음'}</small></button></li>)}</ul>}
 <p className="caption">읽음 표시는 이 브라우저의 역할별로 저장됩니다. 첫 조회의 기존 기록은 새 알림에 포함하지 않습니다.</p></section>}
 </div>
}
