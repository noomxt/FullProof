/** Requires the local launcher with --fixture. Signs via Hardhat RPC only. */
import assert from 'node:assert/strict';
import {JsonRpcProvider,Contract} from 'ethers';
import {readFileSync,writeFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';
process.chdir(fileURLToPath(new URL('../',import.meta.url)));
const base='http://127.0.0.1:8000/api/v1';
async function api(path,body,expected=200){
  const response=await fetch(base+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();assert.equal(response.status,expected,JSON.stringify(data));return data;
}
const status=await api('/system/status');
assert.equal(status.execution.provider,'fixture');assert.equal(status.chain.chain_id,31337);
if(process.argv.includes('--verify-stale')){
  const previous=JSON.parse(readFileSync('../docs/LOCAL_TEST_EVIDENCE.json','utf8'));
  for(const record of previous.transactions){
    const state=await api(`/ai/anchor-status/${record.analysis_id}`);
    assert.equal(state.anchor_status,'STALE_CHAIN');
  }
  console.log('PASS: previous local-chain confirmations are not shown as current-chain confirmations after restart');
  process.exit(0);
}
const provider=new JsonRpcProvider('http://127.0.0.1:8545');
const signer=await provider.getSigner(1);
const agency=await signer.getAddress();
const artifact=JSON.parse(readFileSync('artifacts/contracts/ChainOfInvestigation.sol/ChainOfInvestigation.json','utf8'));
const contract=new Contract(status.chain.contract_address,artifact.abi,provider);
const scenarios=(await api('/demo/scenarios')).scenarios;
assert.equal((await api('/demo/bootstrap',{})).seeded,4);
const results=[],transactions=[];
for(const scenario of scenarios){
  const request={request_id:randomUUID(),case_id:scenario.case_id,step_id:scenario.step_id,claim_id:scenario.id,claim_version:1,raw_claim_text:scenario.raw_claim_text,proof:scenario.proof,evidence:[]};
  if(scenario.id==='match'){
    const normal=(await api('/ai/analyses',request)).analysis;
    assert.equal(normal.verdict,'INSUFFICIENT');
    results.push('Independent proof validation absent: normal analysis stays INSUFFICIENT');
  }
  const draft=(await api('/ai/drafts',request)).analysis;
  assert.equal(draft.verdict,scenario.expected_verdict,scenario.id);
  assert.equal(draft.execution.is_simulated,true);
  assert.equal(draft.is_provisional,true);
  assert.equal((await api('/ai/drafts',request)).analysis.analysis_id,draft.analysis_id);
  const nonce=Number((await api(`/blockchain/agencies/${agency}`)).nonce);
  const body={analysis_id:draft.analysis_id,agency,nonce,deadline:Math.floor(Date.now()/1000)+600,evidence_timestamp:Math.floor(Date.parse(scenario.proof?.occurred_at||'2026-10-10T14:00:00+09:00')/1000),signature:''};
  if(scenario.expected_verdict==='INSUFFICIENT'){
    await api(`/ai/drafts/${draft.analysis_id}/signing-payload`,body,409);
    assert.equal((await api(`/ai/anchor-status/${draft.analysis_id}`)).anchor_status,'NOT_REQUESTED');
    results.push(`${scenario.id}: INSUFFICIENT, no signing payload or fabricated transaction`);
    continue;
  }
  const payload=await api(`/ai/drafts/${draft.analysis_id}/signing-payload`,body);
  if(scenario.id==='match'){
    const tampered=await signer.signTypedData(payload.domain,payload.types,{...payload.message,result:2});
    await api('/ai/anchor',{...body,signature:tampered},400);
    assert.equal((await api(`/ai/anchor-status/${draft.analysis_id}`)).anchor_status,'NOT_REQUESTED');
    results.push('Tampered typed data rejected before anchoring');
  }
  body.signature=await signer.signTypedData(payload.domain,payload.types,payload.message);
  const delivery=await api('/ai/anchor',body);
  assert.equal(delivery.anchor_status,'CONFIRMED');assert.equal(delivery.case_persistence,'SAVED');
  assert.match(delivery.transaction_hash,/^0x[a-f0-9]{64}$/i);
  assert.equal((await api('/ai/anchor',body)).transaction_hash,delivery.transaction_hash);
  const state=await api(`/ai/anchor-status/${draft.analysis_id}`);
  assert.equal(state.anchor_status,'CONFIRMED');assert.equal(state.case_persistence,'SAVED');
  const receipt=await provider.getTransactionReceipt(delivery.transaction_hash);
  assert.equal(receipt.status,1);assert.equal(receipt.to.toLowerCase(),status.chain.contract_address.toLowerCase());
  const caseId=BigInt(payload.message.caseId);
  const history=(await api(`/cases/${scenario.case_id}/steps/${scenario.step_id}/proof-history`));
  assert.equal(history.count,1);
  const record=await contract.getProofRecord(caseId,scenario.step_id,0);
  assert.equal(record[2].toLowerCase(),agency.toLowerCase());
  assert.equal(record[3],payload.message.claimHash);assert.equal(record[4],payload.message.proofHash);
  assert.equal(Number(record[5]),scenario.expected_verdict==='SUPPORTED'?1:2);
  const saved=await api(`/cases/${scenario.case_id}`);
  assert.equal(saved.steps[scenario.step_id].status,scenario.expected_verdict==='SUPPORTED'?'VERIFIED':'MISMATCH');
  const staleDraft=(await api('/ai/drafts',{...request,request_id:randomUUID()})).analysis;
  const staleBody={...body,analysis_id:staleDraft.analysis_id};
  const stalePayload=await api(`/ai/drafts/${staleDraft.analysis_id}/signing-payload`,staleBody);
  staleBody.signature=await signer.signTypedData(stalePayload.domain,stalePayload.types,stalePayload.message);
  await api('/ai/anchor',staleBody,400);
  assert.equal((await api(`/cases/${scenario.case_id}/steps/${scenario.step_id}/proof-history`)).count,1);
  results.push(`${scenario.id}: typed signature -> real local receipt -> immutable proof history -> SQLite; duplicate/reused nonce rejected`);
  transactions.push({scenario:scenario.id,analysis_id:draft.analysis_id,transaction_hash:delivery.transaction_hash,block_number:receipt.blockNumber});
}
const sample=scenarios[0];
await api('/ai/drafts',{request_id:randomUUID(),case_id:sample.case_id,step_id:sample.step_id,claim_id:'invalid',claim_version:1,raw_claim_text:'unsupported fixture input',proof:sample.proof,evidence:[]},422);
results.push('Unlisted fixture text fails explicitly; no invented model output');
const evidence={tested_at:new Date().toISOString(),environment:'LOCAL_HARDHAT_CHAIN_31337',ai_provider:'fixture (no Gemini call)',contract_address:status.chain.contract_address,results,transactions};
writeFileSync('../docs/LOCAL_TEST_EVIDENCE.json',JSON.stringify(evidence,null,2));
for(const result of results)console.log('PASS:',result);
console.log('PASS: four scenarios and live local blockchain signed-record checks');
