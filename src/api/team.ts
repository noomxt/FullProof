export interface TeamCase {
  case_id:string; title:string; is_closed:boolean;
  steps:{step_id:number; step_name:string; status?:string}[];
}
export interface Execution {provider:string; is_simulated:boolean; label:string}
export interface FieldCheck {field:string; claim_value:unknown; proof_value:unknown; status:string; reason_code:string}
export interface ActionResult {field_checks?:FieldCheck[]; reason_text?:string; semantic_result?:unknown}
export interface Analysis {
  analysis_id:string; case_id:string; step_id:number; verdict:string|null;
  processing_status:string; reason_text:string; structured_claim:unknown;
  action_results:ActionResult[]; is_provisional?:boolean; trust_status?:string;
  error_code?:string; execution?:Execution; evaluated_at?:string;
}
export interface Delivery {
  anchor_status:string; transaction_hash?:string; trust_status?:string;
  case_persistence?:string; recovery_required?:boolean;
}
export interface SystemStatus {
  environment:string; execution:Execution; ai_ready:boolean; gemini_key_configured:boolean;
  model:string; case_count:number;
  chain:{ready:boolean; chain_id:number|null; block_number:number|null; contract_address:string|null};
  local_demo:{agency_address:string; signer_address:string; rpc_url:string}|null;
}
export interface Scenario {id:string; case_id:string; title:string; label:string; step_id:number; raw_claim_text:string; proof:Record<string,unknown>|null; expected_verdict:string}
export class TeamError extends Error {
  constructor(message:string,public detail:unknown,public status?:number){super(message)}
}
export async function teamRequest<T>(path:string,body?:unknown):Promise<T>{
  const base=(import.meta.env.VITE_TEAM_API_URL||'http://127.0.0.1:8000').replace(/\/$/,'');
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),240000);
  try {
    const response=await fetch(base+'/api/v1'+path,{
      method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},
      body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal
    });
    const payload=await response.json();
    if(!response.ok)throw new TeamError(typeof payload.detail==='string'?payload.detail:`요청 실패 (${response.status})`,payload.detail,response.status);
    return payload as T;
  } catch(error) {
    if(error instanceof DOMException&&error.name==='AbortError')throw new Error('서버 응답 시간이 초과되었습니다. 저장 요청이었다면 저장 상태를 먼저 조회해 주세요.');
    if(error instanceof TypeError)throw new Error('백엔드에 연결할 수 없습니다. 서버 실행 상태와 VITE_TEAM_API_URL을 확인해 주세요.');
    throw error;
  } finally { clearTimeout(timer) }
}
interface Wallet {request(args:{method:string;params?:unknown[]}):Promise<unknown>}
function wallet():Wallet {
  const ethereum=(window as unknown as {ethereum?:Wallet}).ethereum;
  if(!ethereum)throw new Error('MetaMask를 설치한 브라우저에서 실행해 주세요.');
  return ethereum;
}
export async function connectLocalWallet(){
  const ethereum=wallet();
  try { await ethereum.request({method:'wallet_switchEthereumChain',params:[{chainId:'0x7a69'}]}) }
  catch(error){
    if((error as {code?:number}).code!==4902)throw error;
    await ethereum.request({method:'wallet_addEthereumChain',params:[{
      chainId:'0x7a69',chainName:'FullProof Local Hardhat',rpcUrls:['http://127.0.0.1:8545'],
      nativeCurrency:{name:'Local test ETH',symbol:'ETH',decimals:18}
    }]});
  }
  return await ethereum.request({method:'eth_requestAccounts'}) as string[];
}
export async function signPayload(payload:{domain:Record<string,unknown>;types:Record<string,unknown>;message:Record<string,unknown>},agency:string,expectedSigner=agency){
  const ethereum=wallet();
  const accounts=await ethereum.request({method:'eth_requestAccounts'}) as string[];
  if(accounts[0]?.toLowerCase()!==expectedSigner.toLowerCase())throw new Error(`체인에 등록된 서명자 계정을 선택해 주세요: ${expectedSigner}`);
  const chain=await ethereum.request({method:'eth_chainId'}) as string;
  if(BigInt(chain)!==BigInt(String(payload.domain.chainId)))throw new Error('백엔드와 지갑의 네트워크가 다릅니다. 지갑 네트워크 연결 버튼을 눌러 주세요.');
  return await ethereum.request({method:'eth_signTypedData_v4',params:[accounts[0],JSON.stringify({
    ...payload,primaryType:'Proof',types:{...payload.types,EIP712Domain:[
      {name:'name',type:'string'},{name:'version',type:'string'},
      {name:'chainId',type:'uint256'},{name:'verifyingContract',type:'address'}
    ]}
  })]}) as string;
}
