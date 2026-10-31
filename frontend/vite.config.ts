import {defineConfig,loadEnv,type Plugin} from 'vite';
import react from '@vitejs/plugin-react';
const readMethods=new Set(['eth_chainId','net_version','web3_clientVersion','eth_blockNumber','eth_getBlockByNumber','eth_getBlockByHash','eth_getBalance','eth_getCode','eth_call','eth_estimateGas','eth_gasPrice','eth_feeHistory','eth_maxPriorityFeePerGas','eth_getTransactionCount','eth_getTransactionByHash','eth_getTransactionReceipt','eth_getLogs','eth_getStorageAt','eth_accounts']);
// Read-only RPC for wallet network discovery. No unlocked signing or submissions.
function readOnlyRpc(target:string):Plugin{
 return {name:'fullproof-read-only-rpc',configureServer(server){server.middlewares.use('/rpc',async(req,res)=>{
  res.setHeader('Content-Type','application/json');res.setHeader('Access-Control-Allow-Origin','*');res.setHeader('Access-Control-Allow-Headers','Content-Type');res.setHeader('Access-Control-Allow-Methods','POST, OPTIONS');
  if(req.method==='OPTIONS'){res.statusCode=204;res.end();return}
  if(req.method!=='POST'){res.statusCode=405;res.end(JSON.stringify({error:'POST required'}));return}
  try{
   let body='';for await(const chunk of req){body+=chunk;if(body.length>262144)throw Error('RPC request too large')}
   const value=JSON.parse(body),calls=Array.isArray(value)?value:[value];
   if(!calls.length||calls.length>50||calls.some(c=>!c||typeof c.method!=='string'||!readMethods.has(c.method))){res.statusCode=403;res.end(JSON.stringify({jsonrpc:'2.0',id:null,error:{code:-32601,message:'Read-only demo RPC: method not allowed'}}));return}
   const upstream=await fetch(target,{method:'POST',headers:{'Content-Type':'application/json'},body,signal:AbortSignal.timeout(15000)});
   res.statusCode=upstream.status;res.end(await upstream.text());
  }catch{res.statusCode=502;res.end(JSON.stringify({jsonrpc:'2.0',id:null,error:{code:-32000,message:'Demo RPC unavailable'}}))}
 })}};
}
export default defineConfig(({mode})=>{
 const env=loadEnv(mode,process.cwd(),'');
 return {plugins:[react(),readOnlyRpc(env.VITE_RPC_TARGET||'http://127.0.0.1:8545')],server:{port:5173,strictPort:true,allowedHosts:['terminal.local'],proxy:{'/backend':{target:env.VITE_BACKEND_TARGET||'http://127.0.0.1:8000',changeOrigin:true,rewrite:p=>p.replace(/^\/backend/,'')}}}};
});
