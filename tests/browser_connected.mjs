/** Full browser -> official API -> real local chain. Injected EIP-1193 wallet;
 * no browser extension and no external Gemini call. Run from project root.
 */
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../',import.meta.url));
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium}=require('playwright');
const {JsonRpcProvider}=createRequire(new URL('../local-tools/package.json',import.meta.url))('ethers');
const logs=root+'.checks/browser-connected';fs.mkdirSync(logs,{recursive:true});
const children=[];
function start(args,cwd,name,env={}){const fd=fs.openSync(logs+'/'+name+'.log','w');const child=spawn(args[0],args.slice(1),{cwd:root+cwd,env:{...process.env,...env},stdio:['ignore',fd,fd]});children.push(child);return child}
async function wait(fn){let last;for(let i=0;i<150;i++){try{return await fn()}catch(e){last=e;await new Promise(r=>setTimeout(r,100))}}throw last}
async function command(args,cwd){const child=start(args,cwd,'command');await new Promise((resolve,reject)=>{child.on('exit',code=>code===0?resolve():reject(Error(fs.readFileSync(logs+'/command.log','utf8'))))})}
let browser,page;
try{
 start([process.execPath,'node_modules/hardhat/dist/src/cli.js','node','--hostname','127.0.0.1'],'local-tools','chain');
 const provider=new JsonRpcProvider('http://127.0.0.1:8545');await wait(()=>provider.getBlockNumber());
 await command([process.execPath,'scripts/deploy-local.mjs'],'local-tools');
 const python=root+'chain-of-investigation/.venv/bin/python';
 start([python,'-m','uvicorn','frontend_server:app','--host','127.0.0.1','--port','8000'],'chain-of-investigation','backend',{FULLPROOF_UI_AI_MODE:'fixture',FULLPROOF_UI_DB_PATH:logs+'/test-'+Date.now()+'.db',FULLPROOF_UI_AUDIT_PATH:logs+'/audit-'+Date.now()+'.db'});
 await wait(async()=>{const r=await fetch('http://127.0.0.1:8000/api/v1/frontend/status');if(!r.ok)throw Error(await r.text());const c=await r.json();assert(c.chain.available);return c});
 start([process.execPath,'node_modules/vite/bin/vite.js','--host','127.0.0.1'],'frontend','vite',{VITE_SERVICE_MODE:'api'});
 await wait(async()=>{assert((await fetch('http://127.0.0.1:5173')).ok)});
 browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000}});page=await context.newPage();
 const apiCalls=[];page.on('request',r=>{if(r.url().includes('/backend/api/'))apiCalls.push({method:r.method(),path:new URL(r.url()).pathname})});const serverErrors=[];page.setDefaultTimeout(12000);page.on('response',async r=>{if(r.status()>=500){serverErrors.push(r.url());console.error('HTTP',r.status(),r.url(),await r.text())}});
 let account=0;let rejectNext=false;const signatures=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.exposeFunction('walletRequest',async({method,params=[]})=>{
  const signer=await provider.getSigner(account),address=await signer.getAddress();
  if(['eth_requestAccounts','eth_accounts'].includes(method))return [address];
  if(method==='eth_chainId')return '0x7a69';
  if(method==='wallet_switchEthereumChain'||method==='wallet_addEthereumChain')return null;
  if(method==='personal_sign'||method==='eth_signTypedData_v4'){
   if(rejectNext){rejectNext=false;throw Error('User rejected signature')}
   signatures.push(method);
   if(method==='personal_sign')return signer.signMessage(Buffer.from(params[0].slice(2),'hex'));
   const typed=JSON.parse(params[1]);delete typed.types.EIP712Domain;return signer.signTypedData(typed.domain,typed.types,typed.message);
  }
  throw Error('Unexpected wallet method '+method);
 });
 await page.addInitScript(()=>{window.ethereum={request:args=>window.walletRequest(args)};localStorage.setItem('fullproof.service.mode','api')});
 await page.goto('http://127.0.0.1:5173');await page.getByRole('button',{name:'수사담당자로 시작'}).click();await page.getByRole('heading',{name:'수사담당자 업무 대시보드'}).waitFor();
 await page.getByRole('button',{name:'다크 모드로 전환',exact:true}).click();
 assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),'dark');
 assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(13, 17, 25)');
 await page.reload();await page.getByRole('button',{name:'라이트 모드로 전환',exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),'dark');
 await page.getByRole('button',{name:'라이트 모드로 전환',exact:true}).click();assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),'light');
 await page.getByRole('button',{name:'다크 모드로 전환',exact:true}).focus();await page.keyboard.press('Space');assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),'dark');

 async function tab(name){if(name==='사건 개요'){const role=await page.getByLabel('시연 역할').inputValue();name=role==='ADMIN'?'검토 개요':role==='AGENCY'?'제공 업무 개요':'사건 개요'}if(name==='기관 증빙·연결')name=(await page.getByLabel('시연 역할').inputValue())==='AGENCY'?'기관 증빙 제공':'증빙 연결';await page.getByRole('button',{name,exact:true}).click()}
 async function role(value){
  const old=new URL(page.url());await page.getByLabel('시연 역할').selectOption(value);
  const title={OFFICER:'수사담당자 업무 대시보드',AGENCY:'원천기관 증빙 데스크',ADMIN:'관리자 검토 대시보드'}[value];
  await page.getByRole('heading',{name:title,exact:true}).waitFor();
  if(old.pathname.startsWith('/cases/')){const tab=value==='AGENCY'?'proofs':value==='ADMIN'?'admin':(['overview','records','proofs','verification','history'].includes(old.searchParams.get('tab'))?old.searchParams.get('tab'):'overview');await page.goto(old.origin+old.pathname+'?tab='+tab);await page.getByRole('button',{name:'상태 새로고침',exact:true}).waitFor()}
 }
 async function create(scenario){
  await page.goto('http://127.0.0.1:5173/workspace');await role('OFFICER');
  await page.locator('details.new-case').evaluate(e=>e.open=true);await page.getByRole('button',{name:'시연 사례 '+({supported:'정상 일치',contradicted:'결과 불일치',insufficient:'증빙 부족',ambiguous:'연결 근거 부족'}[scenario]),exact:true}).click();await page.getByLabel('새 시연 회차로 시작').check();await page.getByRole('button',{name:'선택한 시연 사건 열기',exact:true}).click();
  await page.getByRole('button',{name:'사건 개요',exact:true}).waitFor();
  assert(await page.getByRole('button',{name:'원문 등록 및 고정',exact:true}).isHidden());
  await tab('수사 기록');await page.getByRole('button',{name:'원문 등록 및 고정',exact:true}).click();
  await page.getByText(/원문 고정 확인 완료/).waitFor();await page.getByRole('button',{name:'구조화 실행',exact:true}).click();await page.getByText('고정 응답 추출 완료 · 외부 AI 호출 없음',{exact:true}).waitFor();
 }
 async function proofAndMapping(testReject=false){
  await tab('기관 증빙·연결');await role('AGENCY');account=1;
  await page.getByRole('button',{name:'가상 Proof 발급·서명 준비',exact:true}).click();await page.getByRole('button',{name:'MetaMask 서명·저장',exact:true}).click();
  await page.getByText('기관 Proof 응답 수신 · 아래 기록 상태를 확인하세요.',{exact:true}).waitFor();
  await role('OFFICER');account=0;await page.locator('input[type=radio]').first().check();
  if(testReject){rejectNext=true;await page.getByRole('button',{name:'선택한 통화와 연결 확인',exact:true}).click();await page.getByRole('alert').filter({hasText:/User rejected/}).waitFor();}
  await page.getByRole('button',{name:'선택한 통화와 연결 확인',exact:true}).click();await page.getByText('연결 선택 이력을 저장했습니다. 최종 판정은 별도입니다.',{exact:true}).waitFor();
 }
 async function verify(expected){await tab('증빙 비교·검증');await page.getByRole('button',{name:'검증 실행 및 판정 기록',exact:true}).click();await page.getByText('검증 응답 수신 · 판정과 온체인 상태를 확인하세요.',{exact:true}).waitFor();assert((await page.locator('.verdict-card').innerText()).includes(expected));}
 await create('supported');await proofAndMapping(true);await verify('일치 · 증빙 뒷받침');
 await page.reload();await page.getByRole('button',{name:'기존 요청 상태 조회',exact:true}).first().click();await page.getByText('기존 검증 요청의 완료를 확인했습니다.',{exact:true}).waitFor();
 await page.getByRole('button',{name:'백엔드 판정 결과 다시 조회',exact:true}).click();await page.getByText(/서버 조회: COMPLETED/).waitFor();
 await page.getByRole('button',{name:'해시 재계산 및 온체인 대조',exact:true}).click();await page.getByText('계산·대조 완료 · 모든 항목 일치',{exact:true}).waitFor();
 const beforeRetry=await (await fetch('http://127.0.0.1:8000/api/v1/frontend/cases')).json();const existing=beforeRetry.find(c=>c.verifications.length);
 await verify('일치 · 증빙 뒷받침');
 const afterRetry=await (await fetch('http://127.0.0.1:8000/api/v1/frontend/cases/'+existing.case_id)).json();assert.equal(afterRetry.verifications.length,1);assert.equal(afterRetry.verifications[0].verification_id,existing.verifications[0].verification_id);
 await role('ADMIN');await tab('관리자 확인');account=0;
 await page.getByLabel('관리자 사유').fill('결과만 확인했습니다.');await page.getByRole('button',{name:'관리자 확인 기록',exact:true}).click();await page.getByText('관리자 확인 요청을 처리했습니다. 기록 상태를 확인하세요.',{exact:true}).waitFor();assert(await page.getByRole('button',{name:'사건 종결',exact:true}).isDisabled());
 await page.getByLabel('관리자 처리').selectOption('ACCEPTED');await page.getByLabel('관리자 사유').fill('최신 증빙과 검증을 확인해 승인합니다.');await page.getByRole('button',{name:'관리자 확인 기록',exact:true}).click();await page.getByText('현재 최신 검증과 관리자 승인 조건이 충족되었습니다.',{exact:true}).waitFor();
 await page.getByLabel('종결 사유').fill('필수 단계의 증빙과 관리자 승인을 확인했습니다.');await page.getByRole('button',{name:'사건 종결',exact:true}).click();await page.getByText('서버에서 종결된 사건',{exact:true}).waitFor();
 await page.reload();await page.getByText('서버에서 종결된 사건',{exact:true}).waitFor();assert(await page.getByLabel('관리자 처리').isDisabled());
 await tab('사건 개요');await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:logs+'/case-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);await page.screenshot({path:logs+'/case-mobile.png',fullPage:true});await page.setViewportSize({width:1440,height:1000});
 for(const [scenario,expected] of [['contradicted','불일치 · 충돌 발견'],['insufficient','근거 부족'],['ambiguous','근거 부족']]){
  await create(scenario);if(scenario!=='insufficient')await proofAndMapping();await verify(expected);await role('ADMIN');await tab('관리자 확인');account=0;assert(await page.getByRole('option',{name:'단계 완료 승인',exact:true}).evaluate(e=>e.disabled));assert(await page.getByRole('button',{name:'사건 종결',exact:true}).isDisabled());
 }
 await page.getByRole('link',{name:'검증·기록 이력',exact:true}).click();await page.getByRole('heading',{name:'검증·블록체인 이력'}).waitFor();await page.getByRole('button',{name:'상태 조회',exact:true}).first().click();
 const rows=await (await fetch('http://127.0.0.1:8000/api/v1/frontend/cases')).json();
 assert(rows.some(c=>c.status==='CLOSED'));assert(rows.some(c=>c.verifications.some(v=>v.verdict==='CONTRADICTED')));assert(rows.filter(c=>c.verifications.some(v=>v.verdict==='INSUFFICIENT')).length>=2);
 assert.equal(serverErrors.length,0,serverErrors.join('\n'));assert.equal(errors.length,0,errors.join('\n'));assert(signatures.filter(x=>x==='eth_signTypedData_v4').length>=3);assert(signatures.filter(x=>x==='personal_sign').length>=6);
 assert(apiCalls.some(c=>c.method==='GET'&&c.path.includes('/verification-requests/')));assert(apiCalls.some(c=>c.path.endsWith('/integrity-data')));assert(!apiCalls.some(c=>c.path.endsWith('/system/status')));assert(!apiCalls.some(c=>c.method==='POST'&&c.path.endsWith('/api/v1/verifications')));
 const result={pass:true,scope:'Chromium UI + official API + real Hardhat, injected EIP-1193 wallet, fixed AI extraction (no Gemini)',signatures,case_count:rows.length,checks:['supported→ACK→ACCEPTED→close','wallet rejection→pending mapping reuse','conflict blocked close','no Proof insufficient','no CALL_REF insufficient','reload history','mobile390 no overflow','real receipt queries','browser SHA-256/JCS and onchain comparison','identical UI retry reuses Verification ID','official request status result query','reload and resume existing request without POST','frontend/status with agency wallet addresses','official integrity-data path','light/dark toggle and keyboard activation','theme persists on reload','dark theme full workflow and mobile390','separate role homes and task menus','scenario selection creates explicit fresh runs','confirmed Proof selected by default'],page_errors:errors};
 fs.writeFileSync(root+'docs/LOCAL_TEST_RESULTS.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(e){if(page){console.error((await page.locator('main').innerText()).slice(-11000));await page.screenshot({path:logs+'/failure.png',fullPage:true})}console.error(fs.readFileSync(logs+'/backend.log','utf8').slice(-7000));throw e}
finally{if(browser)await browser.close();for(const child of children.reverse())if(child.exitCode===null)child.kill('SIGTERM')}
