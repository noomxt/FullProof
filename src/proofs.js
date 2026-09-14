const encode = value => new TextEncoder().encode(JSON.stringify(value));
const hex = bytes => Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');
const unhex = value => Uint8Array.from(value.match(/.{2}/g) ?? [], b => parseInt(b, 16));
export async function issueProof(step, keys) {
  if (step.proof.kind === 'no_response') return {pending: true, issuer: step.issuer};
  if (!keys[step.issuer]) keys[step.issuer] = await crypto.subtle.generateKey({name:'ECDSA', namedCurve:'P-256'}, true, ['sign','verify']);
  const payload = {step_id:step.id, ...step.proof, issued_at:new Date().toISOString()};
  const data = encode(payload);
  const signature = hex(await crypto.subtle.sign({name:'ECDSA', hash:'SHA-256'}, keys[step.issuer].privateKey, data));
  const hash = hex(await crypto.subtle.digest('SHA-256', data));
  return {payload, signature, hash, publicKey:await crypto.subtle.exportKey('jwk', keys[step.issuer].publicKey), key_type:'ephemeral-browser-demo'};
}
export async function validateProof(receipt, step, keys) {
  if (!receipt || receipt.pending) return false;
  if (receipt.payload.issuer !== step.issuer || receipt.payload.step_id !== step.id || !keys[step.issuer]) return false;
  const data = encode(receipt.payload);
  const hash = hex(await crypto.subtle.digest('SHA-256', data));
  return hash === receipt.hash && crypto.subtle.verify({name:'ECDSA', hash:'SHA-256'}, keys[step.issuer].publicKey, unhex(receipt.signature), data);
}
