import hre from "hardhat";
import { ethers } from "ethers";
import { readFileSync } from "node:fs";

// .env에서 배포된 컨트랙트 주소 읽기
const envText = readFileSync(".env", "utf8");
const match = envText.match(/^CONTRACT_ADDRESS\s*=\s*(.+)$/m);

if (!match) {
  throw new Error(".env에 CONTRACT_ADDRESS가 없습니다.");
}

const contractAddress = match[1].trim().replace(/^["']|["']$/g, "");

async function main() {
  const artifact = await hre.artifacts.readArtifact(
    "contracts/ChainOfInvestigation.sol:ChainOfInvestigation"
  );

  const provider = new ethers.JsonRpcProvider(
    "http://127.0.0.1:8545"
  );

  // Hardhat 로컬 블록체인의 관리자 계정
  const admin = await provider.getSigner(0);

  const contract = new ethers.Contract(
    contractAddress,
    artifact.abi,
    admin
  );

  const adminAddress = await admin.getAddress();
  const onchainAdmin = await contract.admin();

  if (adminAddress.toLowerCase() !== onchainAdmin.toLowerCase()) {
    throw new Error("현재 계정은 컨트랙트 관리자가 아닙니다.");
  }

  const agencies = [
    {
      name: "경찰청",
      address: "0x0B257BB5DCc00Afd085E5FD3ab57D6724073A71C",
      type: 1,
    },
    {
      name: "이동통신사",
      address: "0x29381A91190877e47CA96aF56F948cc579b7eCA1",
      type: 2,
    },
    {
      name: "관제센터",
      address: "0x24C2715bB8d4c3d85D76105AC5D8EA470445A20A",
      type: 3,
    },
  ];

  for (const agency of agencies) {
    const alreadyRegistered =
      await contract.isAuthorizedAgency(agency.address);

    if (alreadyRegistered) {
      console.log(`${agency.name}: 이미 등록되어 있습니다.`);
      continue;
    }

    const tx = await contract.registerAgency(
      agency.address,
      agency.type,
      agency.address
    );

    const receipt = await tx.wait();

    if (!receipt || receipt.status !== 1) {
      throw new Error(`${agency.name} 등록 트랜잭션 실패`);
    }

    const authorized =
      await contract.isAuthorizedAgency(agency.address);

    if (!authorized) {
      throw new Error(`${agency.name} 권한 확인 실패`);
    }

    console.log(`${agency.name}: 등록 및 권한 확인 성공`);
    console.log(`TX: ${tx.hash}`);
  }

  console.log("기관 등록 작업 완료");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});