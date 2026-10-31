import {JsonRpcProvider, ContractFactory, Contract,keccak256} from 'ethers';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
process.chdir(fileURLToPath(new URL('../../chain-of-investigation/',import.meta.url)));
const provider=new JsonRpcProvider('http://127.0.0.1:8545');
if((await provider.getNetwork()).chainId!==31337n)throw Error('Local chain 31337 only');
const admin=await provider.getSigner(0),signer=await provider.getSigner(1),agency=await signer.getAddress();
const artifact=JSON.parse(readFileSync('artifacts/contracts/ChainOfInvestigation.sol/ChainOfInvestigation.json','utf8'));
let contract,receipt;
if(existsSync('local-demo.json')){
 const old=JSON.parse(readFileSync('local-demo.json','utf8'));
 try{
  receipt=await provider.getTransactionReceipt(old.deployment_tx);
  if(receipt?.blockHash===old.deployment_block_hash&&old.artifact_hash===keccak256(artifact.bytecode)&&await provider.getCode(old.contract_address)!=='0x'){
   contract=new Contract(old.contract_address,artifact.abi,admin);
  }
 }catch{}
}
if(!contract){contract=await new ContractFactory(artifact.abi,artifact.bytecode,admin).deploy();await contract.waitForDeployment();receipt=await contract.deploymentTransaction().wait();}
if(!(await contract.isAuthorizedAgency(agency)))await(await contract.registerAgency(agency,2,agency)).wait();
if(!(await contract.isVerificationRecorder(agency)))await(await contract.setVerificationRecorder(agency,true)).wait();
const d=await contract.eip712Domain();
writeFileSync('local-demo.json',JSON.stringify({chain_id:31337,contract_address:await contract.getAddress(),agency_address:agency,signer_address:agency,
 deployment_tx:receipt.hash,deployment_block_hash:receipt.blockHash,artifact_hash:keccak256(artifact.bytecode),domain_version:d[2],
 environment:'LOCAL_HARDHAT_DEMO',note:'Synthetic agency, public local test accounts. Not an institutional identity.'},null,2));
console.log('Local v1.1 contract ready:',await contract.getAddress());
console.log('Synthetic agency signer:',agency);
console.log('Actual EIP-712 domain version:',d[2],'(team spec target is 2)');

// Preserve the locally entered Gemini key; write only public local chain settings.
const envPath='.env';
let envText=existsSync(envPath)?readFileSync(envPath,'utf8'):'';
if(envText.includes('\0'))throw Error('Save .env as UTF-8 before deploying.');
const values={RPC_URL:'http://127.0.0.1:8545',CONTRACT_ADDRESS:await contract.getAddress(),UI_AGENCY_ADDRESS:agency,V11_MAPPING_REVIEWERS:await admin.getAddress()};
for(const [key,value] of Object.entries(values)){const expression=new RegExp('^'+key+'=.*$','m');envText=expression.test(envText)?envText.replace(expression,key+'='+value):envText+'\n'+key+'='+value;}
writeFileSync(envPath,envText+'\n','utf8');
