import {JsonRpcProvider, ContractFactory, Contract, keccak256} from 'ethers';
import {readFileSync, writeFileSync, existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
process.chdir(fileURLToPath(new URL('../', import.meta.url)));
const provider = new JsonRpcProvider('http://127.0.0.1:8545');
if ((await provider.getNetwork()).chainId !== 31337n) throw Error('Local Hardhat chain 31337 only');
const admin = await provider.getSigner(0);
const signer = await provider.getSigner(1);
const agency = await signer.getAddress();
const artifact = JSON.parse(readFileSync('artifacts/contracts/ChainOfInvestigation.sol/ChainOfInvestigation.json','utf8'));
let contract;
if (existsSync('local-demo.json')) {
  const old = JSON.parse(readFileSync('local-demo.json','utf8'));
  const code = await provider.getCode(old.contract_address);
  if (code !== '0x' && keccak256(code) === old.runtime_hash && old.artifact_hash === keccak256(artifact.bytecode)) {
    const candidate = new Contract(old.contract_address, artifact.abi, admin);
    if ((await candidate.admin()).toLowerCase() === (await admin.getAddress()).toLowerCase()) contract = candidate;
  }
}
if (!contract) {
  contract = await new ContractFactory(artifact.abi, artifact.bytecode, admin).deploy();
  await contract.waitForDeployment();
}
if (!(await contract.isAuthorizedAgency(agency))) await (await contract.registerAgency(agency, 2, agency)).wait();
const address = await contract.getAddress();
const state = {chain_id:31337,rpc_url:'http://127.0.0.1:8545',contract_address:address,
  agency_address:agency,signer_address:agency,runtime_hash:keccak256(await provider.getCode(address)),artifact_hash:keccak256(artifact.bytecode),environment:'LOCAL_HARDHAT_DEMO',
  note:'Synthetic agency. Public local test accounts only. No institutional identity assertion.'};
writeFileSync('local-demo.json', JSON.stringify(state,null,2));
let env = existsSync('.env') ? readFileSync('.env','utf8') : readFileSync('.env.example','utf8');
for (const [key,value] of Object.entries({RPC_URL:state.rpc_url,CONTRACT_ADDRESS:address,LOCAL_DEMO:'1'})) {
  const re = new RegExp(`^${key}=.*$`, 'm');
  env = re.test(env) ? env.replace(re,`${key}=${value}`) : env+`\n${key}=${value}\n`;
}
writeFileSync('.env',env);
console.log('Local contract ready:', address);
console.log('Registered synthetic agency / signer:', agency);
console.log('Saved .env and public local-demo.json. No private keys written.');
