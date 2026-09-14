import test from 'node:test';
import assert from 'node:assert/strict';
import {createSteps} from '../src/engine.js';
import {issueProof,validateProof} from '../src/proofs.js';

test('issued proof verifies with its institution key and rejects altered evidence', async()=>{
  const step=createSteps()[0], keys={};
  const receipt=await issueProof(step,keys);
  assert.equal(await validateProof(receipt,step,keys),true);
  assert.equal(await validateProof({...receipt,payload:{...receipt.payload,target:'OTHER'}},step,keys),false);
  assert.equal(await validateProof(receipt,{...step,issuer:'MOCK-CCTV'},keys),false);
  assert.equal(await validateProof(receipt,{...step,id:2},keys),false);
  assert.equal(await validateProof(receipt,step,{}),false);
});
test('agency records remain independent of altered claims, and nonresponse issues no proof', async()=>{
  const steps=createSteps(),keys={};
  steps[0].claim.target='WRONG';
  const receipt=await issueProof(steps[0],keys);
  assert.equal(receipt.payload.target,'P-1872');
  const pending=await issueProof(createSteps('deadline')[3],keys);
  assert.equal(pending.pending,true);
  assert.equal(pending.signature,undefined);
});
