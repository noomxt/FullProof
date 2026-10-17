/** Browser wallet adapter signs via the real local RPC; not MetaMask-extension QA. */
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(new URL('../team-backend/package.json',import.meta.url));
const {JsonRpcProvider}=require('ethers');
const provider=new JsonRpcProvider('http://127.0.0.1:8545');
const signer=await provider.getSigner(1),account=await signer.getAddress();
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1100}});
const errors=[];page.on('pageerror',error=>errors.push(error.message));
try{
  await page.exposeFunction('fullproofTestWallet',async({method,params=[]})=>{
    if(method==='eth_requestAccounts')return [account];
    if(method==='eth_chainId')return '0x7a69';
    if(method==='wallet_switchEthereumChain'||method==='wallet_addEthereumChain')return null;
    if(method==='eth_signTypedData_v4')return await provider.send(method,params);
    throw Error(`Unsupported test wallet method ${method}`);
  });
  await page.addInitScript(()=>{window.ethereum={request:args=>window.fullproofTestWallet(args)}});
  await page.goto('http://127.0.0.1:5173/integration');
  await page.getByRole('button',{name:'기록·증빙 일치',exact:true}).click();
  await page.getByRole('button',{name:'기관 서명용 분석 초안 생성'}).click();
  await page.getByText('서명 전 초안',{exact:true}).waitFor();
  await page.getByRole('button',{name:'MetaMask 서명 및 저장 요청'}).click();
  await page.getByText('CONFIRMED',{exact:true}).waitFor({timeout:30000});
  await page.getByText(/로컬 체인 영수증 성공 확인. 사건 저장: SAVED/).waitFor();
  await page.getByRole('button',{name:'저장 상태 다시 조회'}).click();
  await page.getByText(/사건 저장: SAVED/).waitFor();
  await page.getByRole('button',{name:'제공 확인·열람 미확인',exact:true}).click();
  await page.getByRole('button',{name:'기관 서명용 분석 초안 생성'}).click();
  await page.getByRole('heading',{name:'증빙 부족 · 판단 보류'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'MetaMask 서명 및 저장 요청'}).isDisabled(),true);
  assert.equal(await page.getByText('CONFIRMED',{exact:true}).count(),0);
  await page.screenshot({path:process.env.FULLPROOF_SCREENSHOT||'/tmp/fullproof-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'/tmp/fullproof-mobile.png',fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Mobile viewport must not overflow');
  assert.deepEqual(errors,[]);
  console.log('PASS: real browser -> FastAPI -> fixed AI adapter -> wallet RPC signature -> real local chain receipt -> history');
  console.log('PASS: CCTV provision does not enable viewing verification/anchoring; mobile has no horizontal overflow');
}finally{await browser.close();await provider.destroy()}
