import {useEffect,useState} from 'react';
export default function StartupSplash(){const [visible,setVisible]=useState(true);useEffect(()=>{const timer=setTimeout(()=>setVisible(false),1500);return ()=>clearTimeout(timer)},[]);return visible?<div className="startup-splash" aria-hidden="true"><img src="/fullproof-logo.png" alt=""/></div>:null}
