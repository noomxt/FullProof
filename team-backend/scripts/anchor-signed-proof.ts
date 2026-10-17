
import hre from "hardhat";
import { ethers } from "ethers";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";

async function main() {
  // 1. .env에서 배포된 컨트랙트 주소 가져오기
  const envText = readFileSync(".env", "utf8");

  const addressMatch = envText.match(
    /^CONTRACT_ADDRESS\s*=\s*(.+)$/m
  );

  if (!addressMatch) {
    throw new Error(".env에 CONTRACT_ADDRESS가 없습니다.");
  }

  const contractAddress = addressMatch[1]
    .trim()
    .replace(/^["']|["']$/g, "");

  // 2. MetaMask로 서명한 데이터 읽기
  const proof = JSON.parse(
    readFileSync("signed-proof.local.json", "utf8")
  );

  const provider = new ethers.JsonRpcProvider(
    "http://127.0.0.1:8545"
  );

  const sender = await provider.getSigner(0);
  const network = await provider.getNetwork();

  if (network.chainId !== 31337n) {
    throw new Error("Hardhat Local 네트워크가 아닙니다.");
  }

  // 3. 컨트랙트 연결
  const artifact = await hre.artifacts.readArtifact(
    "contracts/ChainOfInvestigation.sol:ChainOfInvestigation"
  );

  const contract = new ethers.Contract(
    contractAddress,
    artifact.abi,
    sender
  );

  const code = await provider.getCode(contractAddress);

  if (code === "0x") {
    throw new Error("컨트랙트가 배포되어 있지 않습니다.");
  }

  // 4. main.py와 동일한 방식으로 사건 ID 변환
  const caseId = BigInt(
    "0x" +
    createHash("sha256")
      .update(proof.case_id, "utf8")
      .digest("hex")
  );

  const stepId = BigInt(proof.step_id);
  const nonce = BigInt(proof.nonce);
  const deadline = BigInt(proof.deadline);
  const evidenceTimestamp = BigInt(proof.evidence_timestamp);

  // 5. 서명 유효기간 확인
  const now = BigInt(
    Math.floor(Date.now() / 1000)
  );

  if (deadline < now) {
    throw new Error(
      "서명이 만료되었습니다. MetaMask에서 다시 서명해주세요."
    );
  }

  // 6. 기관 등록 여부 확인
  const authorized =
    await contract.isAuthorizedAgency(proof.agency);

  if (!authorized) {
    throw new Error("등록되지 않은 기관입니다.");
  }

  // 7. nonce 확인
  const currentNonce =
    await contract.agencyNonces(proof.agency);

  if (currentNonce !== nonce) {
    throw new Error(
      `nonce 불일치: 현재 ${currentNonce}, 서명 ${nonce}`
    );
  }

  // 8. 서명자 복구 및 확인
  const request = {
    caseId,
    stepId,
    claimHash: proof.claim_hash,
    proofHash: proof.proof_hash,
    result: Number(proof.result),
    evidenceTimestamp,
    nonce,
    deadline,
    agency: proof.agency
  };

  const recoveredSigner =
    await contract.recoverProofSigner(
      request,
      proof.signature
    );
    // MetaMask에 실제 전달한 원본 데이터 확인
    if (!proof.signed_typed_data) {
        throw new Error(
            "서명 원본 데이터가 없습니다. HTML에서 다시 서명해주세요."
        );
    }

    const original = proof.signed_typed_data;
    const originalTypes = {
        Proof: original.types.Proof
    };

    // 서명 당시 원본 메시지로 서명자 복구
    const originalSigner = ethers.verifyTypedData(
        original.domain,
        originalTypes,
        original.message,
        proof.signature
    );

    // 서명 원본으로 계산한 해시
    const originalHash = ethers.TypedDataEncoder.hash(
        original.domain,
        originalTypes,
        original.message
    );

    // 현재 스크립트에서 재구성한 메시지의 해시
    const reconstructedHash = ethers.TypedDataEncoder.hash(
        original.domain,
        originalTypes,
        request
    );

    console.log("====== 원본 서명 비교 ======");
    console.log("서명 요청 계정:", proof.signing_account);
    console.log("서명 원본 복구 주소:", originalSigner);
    console.log("서명 원본 해시:", originalHash);
    console.log("재구성 메시지 해시:", reconstructedHash);
    console.log(
        "원본과 재구성 해시 일치:",
        originalHash.toLowerCase() ===
            reconstructedHash.toLowerCase()
    );
    console.log("==========================");

  // 브라우저에서 서명한 EIP-712 데이터 재구성
  const domain = {
    name: "FullProof",
    version: "1",
    chainId: 31337,
    verifyingContract: contractAddress
  };

  const types = {
    Proof: [
      { name: "caseId", type: "uint256" },
      { name: "stepId", type: "uint256" },
      { name: "claimHash", type: "bytes32" },
      { name: "proofHash", type: "bytes32" },
      { name: "result", type: "uint8" },
      { name: "evidenceTimestamp", type: "uint64" },
      { name: "nonce", type: "uint256" },
      { name: "deadline", type: "uint64" },
      { name: "agency", type: "address" }
    ]
  };

  // ethers.js에서 복구한 서명자
  const offchainSigner = ethers.verifyTypedData(
    domain,
    types,
    request,
    proof.signature
  );

  // JavaScript에서 계산한 EIP-712 해시
  const offchainHash = ethers.TypedDataEncoder.hash(
    domain,
    types,
    request
  );

  // Solidity 컨트랙트에서 계산한 EIP-712 해시
  const onchainHash =
    await contract.getProofTypedDataHash(request);

  console.log("====== 서명 원본 데이터 확인 ======");
  console.log("사건 ID:", request.caseId.toString());
  console.log("단계 ID:", request.stepId.toString());
  console.log("Claim 해시:", request.claimHash);
  console.log("Proof 해시:", request.proofHash);
  console.log("검증 결과:", request.result);
  console.log("증거 시각:", request.evidenceTimestamp.toString());
  console.log("Nonce:", request.nonce.toString());
  console.log("Deadline:", request.deadline.toString());
  console.log("기관 주소:", request.agency);
  console.log("==============================");
  console.log("====== EIP-712 비교 ======");
  console.log("관제센터 주소:", proof.agency);
  console.log("JS 복구 서명자:", offchainSigner);
  console.log("Solidity 복구 서명자:", recoveredSigner);
  console.log("JS EIP-712 해시:", offchainHash);
  console.log("Solidity EIP-712 해시:", onchainHash);
  console.log(
    "해시 일치:",
    offchainHash.toLowerCase() === onchainHash.toLowerCase()
  );
  console.log("=========================");


  const agencyInfo = await contract.agencies(proof.agency);
  const registeredSigner = agencyInfo.signer;
  console.log("========== 서명 디버깅 ==========");
  console.log("MetaMask 기관 주소:", proof.agency);
  console.log("컨트랙트 등록 서명자:", registeredSigner);
  console.log("복구된 실제 서명자:", recoveredSigner);
  console.log("컨트랙트 주소:", contractAddress);
  console.log("현재 Chain ID:", network.chainId.toString());
  console.log("================================");

  if (
    recoveredSigner.toLowerCase() !==
    registeredSigner.toLowerCase()
  ) {
    throw new Error("등록된 기관 서명자와 일치하지 않습니다.");
  }

  console.log("기관 전자서명 확인 성공");

  // 9. 트랜잭션 인자 준비
  const args = [
    caseId,
    stepId,
    proof.claim_hash,
    proof.proof_hash,
    Number(proof.result),
    evidenceTimestamp,
    deadline,
    nonce,
    proof.agency,
    proof.signature
  ] as const;

  // 10. 실제 기록 전에 실행 가능 여부 확인
  await contract.anchorProof.staticCall(...args);

  console.log("컨트랙트 사전 검증 성공");

  // 11. 실제 블록체인 트랜잭션 전송
  const tx = await contract.anchorProof(...args);

  console.log("트랜잭션 전송:", tx.hash);

  const receipt = await tx.wait();

  if (!receipt || receipt.status !== 1) {
    throw new Error("블록체인 기록 실패");
  }

  console.log("블록체인 기록 성공!");

  // 12. Proof History 확인
  const historyLength =
    await contract.getProofHistoryLength(caseId, stepId);

  const latest =
    await contract.getLatestProof(caseId, stepId);

  console.log("Proof History 개수:", historyLength.toString());
  console.log("최근 Proof ID:", latest.proofId.toString());
  console.log("최근 검증 상태:", latest.status.toString());
  console.log("서명 기관:", latest.agency);
  console.log("기록된 Proof 해시:", latest.proofHash);
}

main().catch(error => {
  console.error("오류:", error.message);
  process.exitCode = 1;
});
