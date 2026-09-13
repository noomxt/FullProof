import http from 'node:http';
import {verifyStep,DEMO_TIME} from '../src/engine.js';

// Optional local adapter. This does not issue real proofs or submit transactions.
const server=http.createServer(async(req,res)=>{
 const send=(status,body)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(body));};
 if(req.method==='GET'&&req.url==='/api/health')return send(200,{status:'ok',mode:'demo-rules',ai_connected:false,blockchain_connected:false});
 if(req.method!=='POST'||req.url!=='/api/v1/demo/verify')return send(404,{error:'Not found'});
 let size=0,chunks=[];
 try{for await(const chunk of req){size+=chunk.length;if(size>65536){send(413,{error:'Payload too large'});return}chunks.push(chunk)}
  const {step,now}=JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if(!step||typeof step.claim?.raw!=='string'||typeof step.claim?.target!=='string'||typeof step.proof?.kind!=='string')return send(400,{error:'Invalid structured claim or proof'});
  return send(200,{...verifyStep(step,now??DEMO_TIME),source:'local-api-rules'});
 }catch{return send(400,{error:'Invalid JSON or claim data'})}
});
server.listen(8000,'127.0.0.1',()=>console.log('FullProof demo API: http://127.0.0.1:8000/api/health'));
