import solc from 'solc';
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../', import.meta.url));
process.chdir(root);
const sourceName = 'contracts/ChainOfInvestigation.sol';
const input = {
  language: 'Solidity', sources: {[sourceName]: {content: readFileSync(sourceName, 'utf8')}},
  settings: {optimizer: {enabled: true, runs: 200}, viaIR: true, evmVersion: 'cancun',
    outputSelection: {'*': {'*': ['abi','evm.bytecode.object','evm.deployedBytecode.object']}}}
};
const output = JSON.parse(solc.compile(JSON.stringify(input), {import: name => {
  try { return {contents: readFileSync(path.join(root, 'node_modules', name), 'utf8')}; }
  catch { return {error: `Import not found: ${name}`}; }
}}));
for (const error of output.errors || []) console.error(error.formattedMessage);
if (output.errors?.some(e => e.severity === 'error')) process.exit(1);
const contract = output.contracts[sourceName].ChainOfInvestigation;
const dir = `artifacts/${sourceName}`;
mkdirSync(dir, {recursive:true});
writeFileSync(`${dir}/ChainOfInvestigation.json`, JSON.stringify({
  _format: 'hh-sol-artifact-1', contractName: 'ChainOfInvestigation', sourceName,
  abi: contract.abi, bytecode: '0x'+contract.evm.bytecode.object,
  deployedBytecode: '0x'+contract.evm.deployedBytecode.object,
  linkReferences: {}, deployedLinkReferences: {}, compilerVersion: solc.version()
}, null, 2));
console.log(`Compiled the unchanged team contract with solc ${solc.version()}`);
