// Offline Mock vector check. No wallet, signatures, or network calls.
const fs = require('node:fs');
const path = require('node:path');
const { default: canonicalize } = require('canonicalize');
const { sha256, toUtf8Bytes, TypedDataEncoder } = require('ethers');
const v = JSON.parse(fs.readFileSync(path.join(__dirname, 'vector.json'), 'utf8'));
const p = v.proof_content, m = v.message;
const proofHash = sha256(toUtf8Bytes(canonicalize(p)));
const digest = TypedDataEncoder.hash(v.domain, v.types, m);
const checks = {
  proof_hash: proofHash === m.proofHash,
  digest: digest === v.expected_digest,
  case_id: BigInt(sha256(toUtf8Bytes(p.case_id))).toString() === m.caseId,
  proof_id: sha256(toUtf8Bytes(p.proof_id)) === m.proofIdHash,
  proof_version: String(p.proof_version) === m.proofVersion,
  occurred_at: String(Date.parse(p.proof_occurred_at)/1000) === m.occurredAt,
  issued_at: String(Date.parse(p.proof_issued_at)/1000) === m.issuedAt
};
const result = {proof_hash: proofHash, digest, checks};
fs.writeFileSync(path.join(__dirname, 'javascript-result.json'), JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
if (!Object.values(checks).every(Boolean)) process.exitCode = 1;
