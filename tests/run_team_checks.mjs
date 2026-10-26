/** Official Python checks against a disposable local chain. No live Gemini. */
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs';
const root=fileURLToPath(new URL('../',import.meta.url));
const {JsonRpcProvider}=createRequire(new URL('../local-tools/package.json',import.meta.url))('ethers');
const logs=root+'.checks';fs.mkdirSync(logs,{recursive:true});
const fd=fs.openSync(logs+'/regression-chain.log','w');
const chain=spawn(process.execPath,['node_modules/hardhat/dist/src/cli.js','node','--hostname','127.0.0.1','--port','18545'],{cwd:root+'local-tools',stdio:['ignore',fd,fd]});
const provider=new JsonRpcProvider('http://127.0.0.1:18545');
async function run(name){
 const child=spawn(root+'chain-of-investigation/.venv/bin/python',[name+'.py'],{cwd:root+'chain-of-investigation',env:{...process.env,FULLPROOF_CHAIN_INTEGRATION:'1',FULLPROOF_TEST_RPC_URL:'http://127.0.0.1:18545',FULLPROOF_TEST_REPORT:'final-mentor-frontend-regression.json',PYTHONUTF8:'1'},stdio:['ignore','pipe','pipe']});
 let output='';for(const stream of [child.stdout,child.stderr])stream.on('data',c=>output+=c);
 const code=await new Promise(resolve=>child.on('exit',resolve));fs.writeFileSync(root+'docs/'+name+'.txt',output);console.log(name+' exit '+code+'\n'+output.slice(-1800));if(code!==0)throw Error(name+' failed');
}
try{
 for(let i=0;i<100;i++){try{await provider.getBlockNumber();break}catch{if(i===99)throw Error('chain timeout');await new Promise(r=>setTimeout(r,100))}}
 await run('run_checks');await run('run_mentor_checks');
}finally{provider.destroy();chain.kill('SIGTERM')}
