/** Exact formats from official main.py @019dd0b. Personal-sign payloads use UTF-8 bytes. */
export function canonical(value:unknown):string {
 if(value===null)return 'null';
 if(typeof value==='string') {if(/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(value))throw Error('잘못된 유니코드 문자열');return JSON.stringify(value)}
 if(typeof value==='number'){if(!Number.isSafeInteger(value))throw Error('서명 숫자는 안전한 정수여야 합니다.');return JSON.stringify(value)}
 if(typeof value==='boolean')return String(value);
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(typeof value==='object')return '{'+Object.keys(value as object).sort().map(k=>canonical(k)+':'+canonical((value as Record<string,unknown>)[k])).join(',')+'}';
 throw Error('서명 데이터에 누락된 값이 있습니다.');
}
export function mappingMessage(caseId:string,m:Record<string,unknown>,claimHash:string,proofHash:string,sourceHash:string,note:string){
 return ['FullProof v1.1 Mapping Confirmation',`case_id=${caseId}`,`mapping_id=${m.mapping_id}`,`claim_id=${m.claim_id}`,`claim_version=${m.claim_version}`,`claim_hash=${claimHash}`,`proof_id=${m.proof_id}`,`proof_version=${m.proof_version}`,`proof_hash=${proofHash}`,`evidence_source_sha256=${sourceHash}`,`evidence_note=${note}`,`nonce=${m.confirmation_nonce}`].join('\n');
}
export const reviewMessage=(chain:number,contract:string,id:string,hash:string,data:Record<string,unknown>)=>canonical({purpose:'FullProof v1.1 Administrator Review',chain_id:chain,contract_address:contract,verification_id:id,verification_hash:hash,review_status:data.review_status,reason_code:data.reason_code,reason_text:data.reason_text,signer_address:data.signer_address,nonce:data.nonce,deadline:data.deadline});
export const closeMessage=(chain:number,contract:string,id:string,data:Record<string,unknown>)=>canonical({purpose:'FullProof v1.1 Case Closure',chain_id:chain,contract_address:contract,case_id:id,reason:data.reason,signer_address:data.signer_address,nonce:data.nonce,deadline:data.deadline});
export const utf8Hex=(text:string)=>'0x'+Array.from(new TextEncoder().encode(text),v=>v.toString(16).padStart(2,'0')).join('');
