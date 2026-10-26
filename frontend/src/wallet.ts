import type {Draft,System} from './api';
import {utf8Hex} from './signing';
export interface Provider {request(args:{method:string;params?:unknown[]}):Promise<unknown>}
declare global {interface Window {ethereum?:Provider}}
export async function walletAccount(expected:string|string[],chainId:number,rpc='http://127.0.0.1:8545'){
 const eth=window.ethereum;if(!eth)throw Error('MetaMask 확장 프로그램이 설치된 브라우저에서 열어 주세요.');
 const accounts=await eth.request({method:'eth_requestAccounts'}) as string[];
 const list=Array.isArray(expected)?expected:[expected];
 if(!list.some(v=>v&&v.toLowerCase()===accounts[0]?.toLowerCase()))throw Error(`등록된 서명 계정으로 변경해 주세요: ${list.join(', ')||'서버 계정 설정 필요'}`);
 const wanted='0x'+chainId.toString(16);
 if(await eth.request({method:'eth_chainId'})!==wanted){
  try{await eth.request({method:'wallet_switchEthereumChain',params:[{chainId:wanted}]})}
  catch(e){if((e as {code?:number}).code!==4902)throw e;await eth.request({method:'wallet_addEthereumChain',params:[{chainId:wanted,chainName:'FullProof Local Hardhat',rpcUrls:[rpc],nativeCurrency:{name:'Test ETH',symbol:'ETH',decimals:18}}]});await eth.request({method:'wallet_switchEthereumChain',params:[{chainId:wanted}]})}
 }
 await assertWallet(accounts[0],wanted);return accounts[0];
}
async function assertWallet(account:string,chain:string){const eth=window.ethereum!;const accounts=await eth.request({method:'eth_accounts'}) as string[];if(accounts[0]?.toLowerCase()!==account.toLowerCase()||await eth.request({method:'eth_chainId'})!==chain)throw Error('계정 또는 네트워크가 변경되었습니다. 내용을 확인하고 다시 서명하세요.')}
export async function personal(message:string,account:string,chainId:number){
 const chain='0x'+chainId.toString(16);await assertWallet(account,chain);
 const signature=await window.ethereum!.request({method:'personal_sign',params:[utf8Hex(message),account]}) as string;
 await assertWallet(account,chain);return signature;
}
export async function signTypedProof(draft:Draft){
 const account=await walletAccount(draft.signer_address,draft.typed_data.domain.chainId);
 const typed={...draft.typed_data,types:{EIP712Domain:[{name:'name',type:'string'},{name:'version',type:'string'},{name:'chainId',type:'uint256'},{name:'verifyingContract',type:'address'}],...draft.typed_data.types}};
 const signature=await window.ethereum!.request({method:'eth_signTypedData_v4',params:[account,JSON.stringify(typed)]}) as string;
 await assertWallet(account,'0x'+draft.typed_data.domain.chainId.toString(16));return signature;
}
export async function signedMessage(config:System,role:'reviewer'|'admin',build:(account:string)=>string){
 const c=config.chain;
 if(!c.chain_id||!c.contract_address)throw Error('서버의 체인·컨트랙트 설정을 확인해 주세요.');
 const expected=role==='admin'?[c.admin_address||'']:(c.reviewer_addresses||[]);
 const account=await walletAccount(expected,c.chain_id,c.rpc_url);
 return {account,signature:await personal(build(account),account,c.chain_id)};
}
