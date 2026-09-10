import hre from "hardhat";
import { ethers } from "ethers";

async function main() {
  // Hardhat이 컴파일한 컨트랙트의 ABI와 바이트코드를 가져옵니다.
  const artifact = await hre.artifacts.readArtifact("ChainOfInvestigation");

  // npx hardhat node 로컬 네트워크에 연결합니다.
  const provider = new ethers.JsonRpcProvider("http://127.0.0.1:8545");
  const signer = await provider.getSigner(0); // 0번 가짜 지갑 계정 사용

  // Ethers ContractFactory로 스마트 컨트랙트를 생성 및 배포합니다.
  const factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode, signer);
  const contract = await factory.deploy();
  await contract.waitForDeployment();

  const contractAddress = await contract.getAddress();
  console.log(`Contract deployed to: ${contractAddress}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});