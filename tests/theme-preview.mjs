/** Internal visual check of both theme surfaces in browser Mock mode. */
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs';
const root=fileURLToPath(new URL('../',import.meta.url));
const {chromium}=createRequire(new URL('../frontend/package.json',import.meta.url))('playwright');
fs.mkdirSync(root+'.checks/theme',{recursive:true});
const fd=fs.openSync(root+'.checks/theme/vite.log','w');const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','preview','--host','127.0.0.1','--port','5173'],{cwd:root+'frontend',stdio:['ignore',fd,fd]});
let browser;
try{
 for(let i=0;i<100;i++){try{if((await fetch('http://127.0.0.1:5173')).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
 browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.addInitScript(()=>{localStorage.setItem('fullproof.service.mode','mock')});await page.goto('http://127.0.0.1:5173');await page.getByRole('heading',{name:'사건 관리 대시보드'}).waitFor();await page.getByRole('link',{name:'가상 실종 사건 · 안산 중앙',exact:true}).waitFor();await page.evaluate(()=>document.fonts.ready);console.log(await page.evaluate(()=>({font:getComputedStyle(document.body).fontFamily,loaded:document.fonts.check('14px \"Noto Sans KR Variable\"','사건 관리')})));
 await page.screenshot({path:root+'.checks/theme/light.png',fullPage:true,animations:'disabled'});await page.getByRole('button',{name:'다크 모드로 전환',exact:true}).click();await page.screenshot({path:root+'.checks/theme/dark.png',fullPage:true,animations:'disabled'});
 console.log('Light/dark visual captures ready');
}finally{if(browser)await browser.close();server.kill('SIGTERM')}
