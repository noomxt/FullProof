import {useLayoutEffect,useState} from 'react';
import {Moon,Sun} from 'lucide-react';
import {applyTheme,readTheme} from './theme';
export default function ThemeToggle(){
 const [theme,setTheme]=useState(readTheme);
 useLayoutEffect(()=>applyTheme(theme),[theme]);
 const dark=theme==='dark';
 return <button className="theme-toggle" type="button" aria-label={dark?'라이트 모드로 전환':'다크 모드로 전환'} aria-pressed={dark} title={dark?'흰색 배경으로 전환':'어두운 배경으로 전환'} onClick={()=>setTheme(dark?'light':'dark')}>{dark?<Sun size={16}/>:<Moon size={16}/>}<span>{dark?'라이트 모드':'다크 모드'}</span></button>;
}
