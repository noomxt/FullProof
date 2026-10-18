import { expect } from "chai";
import { network } from "hardhat";

const connection = await network.create();
const { ethers } = connection;

const AGENCY_TYPE = {
  NONE: 0,
  POLICE: 1,
  TELECOM: 2,
  CCTV: 3,
} as const;

const STATUS = {
  PENDING: 0,
  VERIFIED: 1,
  MISMATCH: 2,
  EXPIRING_SOON: 3,
} as const;

const PROOF_TYPES = {
  Proof: [
    { name: "caseId", type: "uint256" },
    { name: "stepId", type: "uint256" },
    { name: "claimHash", type: "bytes32" },
    { name: "proofHash", type: "bytes32" },
    { name: "result", type: "uint8" },
    { name: "evidenceTimestamp", type: "uint64" },
    { name: "nonce", type: "uint256" },
    { name: "deadline", type: "uint64" },
    { name: "agency", type: "address" },
  ],
};

async function makeProofSignature(
  contract: any,
  signer: any,
  request: {
    caseId: bigint;
    stepId: bigint;
    claimHash: string;
    proofHash: string;
    result: number;
    evidenceTimestamp: bigint;
    nonce: bigint;
    deadline: bigint;
    agency: string;
  },
) {
  const networkInfo = await ethers.provider.getNetwork();

  const domain = {
    name: "FullProof",
    version: "1",
    chainId: networkInfo.chainId,
    verifyingContract: await contract.getAddress(),
  };

  return signer.signTypedData(domain, PROOF_TYPES, request);
}

describe("ChainOfInvestigation - FullProof upgraded contract", function () {
  let contract: any;
  let admin: any;
  let police: any;
  let telecom: any;
  let cctv: any;
  let outsider: any;
  let caseId: bigint;

  beforeEach(async function () {
    [admin, police, telecom, cctv, outsider] = await ethers.getSigners();

    contract = await ethers.deployContract("ChainOfInvestigation");
    await contract.waitForDeployment();

    caseId = BigInt(
      ethers.keccak256(ethers.toUtf8Bytes("CASE_2026_001"))
    );

    await contract.createCase(caseId);

    await contract.addStep(
      caseId,
      "보호자 연락 및 안전확인",
      true
    );

    await contract.addStep(
      caseId,
      "관련 CCTV 확인",
      true
    );

    await contract.addStep(
      caseId,
      "추가 참고자료",
      false
    );

    await contract.registerAgency(
      telecom.address,
      AGENCY_TYPE.TELECOM,
      telecom.address
    );

    await contract.registerAgency(
      cctv.address,
      AGENCY_TYPE.CCTV,
      cctv.address
    );

    await contract.registerAgency(
      police.address,
      AGENCY_TYPE.POLICE,
      police.address
    );
  });

  it("1. 사건 생성과 단계 추가가 정상 동작한다", async function () {
    const caseInfo = await contract.cases(caseId);

    expect(caseInfo.exists).to.equal(true);
    expect(caseInfo.stepCount).to.equal(3n);

    const step = await contract.getStepInfo(caseId, 0);

    expect(step[0]).to.equal("보호자 연락 및 안전확인");
    expect(step[3]).to.equal(STATUS.PENDING);
    expect(step[4]).to.equal(false);
    expect(step[5]).to.equal(true);
  });

  it("2. 등록되지 않은 기관은 Proof를 앵커링할 수 없다", async function () {
    const claimHash = ethers.keccak256(
      ethers.toUtf8Bytes("CLAIM")
    );

    const proofHash = ethers.keccak256(
      ethers.toUtf8Bytes("PROOF")
    );

    const request = {
      caseId,
      stepId: 0n,
      claimHash,
      proofHash,
      result: STATUS.VERIFIED,
      evidenceTimestamp: 1750000000n,
      nonce: 0n,
      deadline: BigInt(Math.floor(Date.now() / 1000) + 3600),
      agency: outsider.address,
    };

    const signature = await makeProofSignature(
      contract,
      outsider,
      request
    );

    await expect(
      contract.anchorProof(
        caseId,
        0,
        claimHash,
        proofHash,
        STATUS.VERIFIED,
        request.evidenceTimestamp,
        request.deadline,
        request.nonce,
        outsider.address,
        signature
      )
    ).to.be.revertedWith("Agency is not authorized");
  });

  it("3. 올바른 기관 전자서명이 있으면 Proof가 검증되고 기록된다", async function () {
    const claimHash = ethers.keccak256(
      ethers.toUtf8Bytes("CLAIM_FAMILY_CALL")
    );

    const proofHash = ethers.keccak256(
      ethers.toUtf8Bytes("PROOF_TELECOM_CALL_LOG")
    );

    const networkInfo = await ethers.provider.getNetwork();

    const request = {
      caseId,
      stepId: 0n,
      claimHash,
      proofHash,
      result: STATUS.VERIFIED,
      evidenceTimestamp: 1750000000n,
      nonce: 0n,
      deadline: BigInt(Math.floor(Date.now() / 1000) + 3600),
      agency: telecom.address,
    };

    const signature = await makeProofSignature(
      contract,
      telecom,
      request
    );

    const recovered = await contract.recoverProofSigner(
      request,
      signature
    );

    expect(recovered.toLowerCase()).to.equal(
      telecom.address.toLowerCase()
    );

    expect(networkInfo.chainId).to.be.greaterThan(0n);

    await expect(
      contract.anchorProof(
        caseId,
        0,
        claimHash,
        proofHash,
        STATUS.VERIFIED,
        request.evidenceTimestamp,
        request.deadline,
        request.nonce,
        telecom.address,
        signature
      )
    ).to.emit(contract, "ProofAnchored");

    const step = await contract.getStepInfo(caseId, 0);

    expect(step[1]).to.equal(claimHash);
    expect(step[2]).to.equal(proofHash);
    expect(step[3]).to.equal(STATUS.VERIFIED);
    expect(step[4]).to.equal(true);

    expect(
      await contract.agencyNonces(telecom.address)
    ).to.equal(1n);

    expect(
      await contract.getProofHistoryLength(caseId, 0)
    ).to.equal(1n);

    const proof = await contract.getLatestProof(caseId, 0);

    expect(proof.agency.toLowerCase()).to.equal(
      telecom.address.toLowerCase()
    );

    expect(proof.signer.toLowerCase()).to.equal(
      telecom.address.toLowerCase()
    );

    expect(proof.status).to.equal(
      STATUS.VERIFIED
    );
  });

  it("4. 다른 기관이 만든 서명으로 위장하면 실패한다", async function () {
    const claimHash = ethers.keccak256(
      ethers.toUtf8Bytes("CLAIM")
    );

    const proofHash = ethers.keccak256(
      ethers.toUtf8Bytes("PROOF")
    );

    const request = {
      caseId,
      stepId: 0n,
      claimHash,
      proofHash,
      result: STATUS.VERIFIED,
      evidenceTimestamp: 1750000000n,
      nonce: 0n,
      deadline: BigInt(Math.floor(Date.now() / 1000) + 3600),
      agency: telecom.address,
    };

    // CCTV가 Telecom을 사칭
    const forgedSignature = await makeProofSignature(
      contract,
      cctv,
      request
    );

    await expect(
      contract.anchorProof(
        caseId,
        0,
        claimHash,
        proofHash,
        STATUS.VERIFIED,
        request.evidenceTimestamp,
        request.deadline,
        request.nonce,
        telecom.address,
        forgedSignature
      )
    ).to.be.revertedWith(
      "Invalid electronic signature"
    );
  });

  it("5. 같은 서명의 재사용(Replay Attack)을 차단한다", async function () {
    const claimHash = ethers.keccak256(
      ethers.toUtf8Bytes("CLAIM")
    );

    const proofHash = ethers.keccak256(
      ethers.toUtf8Bytes("PROOF")
    );

    const request = {
      caseId,
      stepId: 0n,
      claimHash,
      proofHash,
      result: STATUS.VERIFIED,
      evidenceTimestamp: 1750000000n,
      nonce: 0n,
      deadline: BigInt(Math.floor(Date.now() / 1000) + 3600),
      agency: telecom.address,
    };

    const signature = await makeProofSignature(
      contract,
      telecom,
      request
    );

    await contract.anchorProof(
      caseId,
      0,
      claimHash,
      proofHash,
      STATUS.VERIFIED,
      request.evidenceTimestamp,
      request.deadline,
      request.nonce,
      telecom.address,
      signature
    );

    await expect(
      contract.anchorProof(
        caseId,
        0,
        claimHash,
        proofHash,
        STATUS.VERIFIED,
        request.evidenceTimestamp,
        request.deadline,
        request.nonce,
        telecom.address,
        signature
      )
    ).to.be.revertedWith(
      "Invalid or used nonce"
    );
  });

  it("6. 만료된 전자서명은 거부한다", async function () {
    const claimHash = ethers.keccak256(
      ethers.toUtf8Bytes("CLAIM")
    );

    const proofHash = ethers.keccak256(
      ethers.toUtf8Bytes("PROOF")
    );

    const request = {
      caseId,
      stepId: 0n,
      claimHash,
      proofHash,
      result: STATUS.VERIFIED,
      evidenceTimestamp: 1750000000n,
      nonce: 0n,
      deadline: 1n,
      agency: telecom.address,
    };

    const signature = await makeProofSignature(
      contract,
      telecom,
      request
    );

    await expect(
      contract.anchorProof(
        caseId,
        0,
        claimHash,
        proofHash,
        STATUS.VERIFIED,
        request.evidenceTimestamp,
        request.deadline,
        request.nonce,
        telecom.address,
        signature
      )
    ).to.be.revertedWith(
      "Signature expired"
    );
  });

  it("7. 재검증이 발생해도 과거 Proof history는 보존된다", async function () {
    const claim1 = ethers.keccak256(
      ethers.toUtf8Bytes("CLAIM_V1")
    );

    const proof1 = ethers.keccak256(
      ethers.toUtf8Bytes("PROOF_V1")
    );

    const claim2 = ethers.keccak256(
      ethers.toUtf8Bytes("CLAIM_V2")
    );

    const proof2 = ethers.keccak256(
      ethers.toUtf8Bytes("PROOF_V2")
    );

    const deadline = BigInt(
      Math.floor(Date.now() / 1000) + 3600
    );

    const request1 = {
      caseId,
      stepId: 0n,
      claimHash: claim1,
      proofHash: proof1,
      result: STATUS.MISMATCH,
      evidenceTimestamp: 1750000000n,
      nonce: 0n,
      deadline,
      agency: telecom.address,
    };

    const sig1 = await makeProofSignature(
      contract,
      telecom,
      request1
    );

    await contract.anchorProof(
      caseId,
      0,
      claim1,
      proof1,
      STATUS.MISMATCH,
      request1.evidenceTimestamp,
      request1.deadline,
      request1.nonce,
      telecom.address,
      sig1
    );

    const request2 = {
      ...request1,
      claimHash: claim2,
      proofHash: proof2,
      result: STATUS.VERIFIED,
      nonce: 1n,
    };

    const sig2 = await makeProofSignature(
      contract,
      telecom,
      request2
    );

    await contract.anchorProof(
      caseId,
      0,
      claim2,
      proof2,
      STATUS.VERIFIED,
      request2.evidenceTimestamp,
      request2.deadline,
      request2.nonce,
      telecom.address,
      sig2
    );

    expect(
      await contract.getProofHistoryLength(caseId, 0)
    ).to.equal(2n);

    const first = await contract.getProofRecord(
      caseId,
      0,
      0
    );

    const latest = await contract.getLatestProof(
      caseId,
      0
    );

    expect(first.status).to.equal(
      STATUS.MISMATCH
    );

    expect(latest.status).to.equal(
      STATUS.VERIFIED
    );

    expect(latest.proofHash).to.equal(
      proof2
    );
  });

  it("8. 필수 단계가 VERIFIED가 아니면 사건을 종결할 수 없다", async function () {
    const claimHash = ethers.keccak256(
      ethers.toUtf8Bytes("CLAIM")
    );

    const proofHash = ethers.keccak256(
      ethers.toUtf8Bytes("PROOF")
    );

    const request = {
      caseId,
      stepId: 0n,
      claimHash,
      proofHash,
      result: STATUS.VERIFIED,
      evidenceTimestamp: 1750000000n,
      nonce: 0n,
      deadline: BigInt(
        Math.floor(Date.now() / 1000) + 3600
      ),
      agency: telecom.address,
    };

    const signature = await makeProofSignature(
      contract,
      telecom,
      request
    );

    await contract.anchorProof(
      caseId,
      0,
      claimHash,
      proofHash,
      STATUS.VERIFIED,
      request.evidenceTimestamp,
      request.deadline,
      request.nonce,
      telecom.address,
      signature
    );

    await expect(
      contract.closeCase(
        caseId,
        "종결 검토"
      )
    ).to.be.revertedWith(
      "Cannot close: required steps must be VERIFIED"
    );
  });

  it("9. 모든 필수 단계가 VERIFIED이면 사건을 종결할 수 있다", async function () {
    const deadline = BigInt(
      Math.floor(Date.now() / 1000) + 3600
    );

    // STEP 0 - Telecom
    const step0 = {
      caseId,
      stepId: 0n,
      claimHash: ethers.keccak256(
        ethers.toUtf8Bytes("CLAIM_0")
      ),
      proofHash: ethers.keccak256(
        ethers.toUtf8Bytes("PROOF_0")
      ),
      result: STATUS.VERIFIED,
      evidenceTimestamp: 1750000000n,
      nonce: 0n,
      deadline,
      agency: telecom.address,
    };

    const sig0 = await makeProofSignature(
      contract,
      telecom,
      step0
    );

    await contract.anchorProof(
      caseId,
      0,
      step0.claimHash,
      step0.proofHash,
      step0.result,
      step0.evidenceTimestamp,
      step0.deadline,
      step0.nonce,
      step0.agency,
      sig0
    );

    // STEP 1 - CCTV
    const step1 = {
      caseId,
      stepId: 1n,
      claimHash: ethers.keccak256(
        ethers.toUtf8Bytes("CLAIM_1")
      ),
      proofHash: ethers.keccak256(
        ethers.toUtf8Bytes("PROOF_1")
      ),
      result: STATUS.VERIFIED,
      evidenceTimestamp: 1750000001n,
      nonce: 0n,
      deadline,
      agency: cctv.address,
    };

    const sig1 = await makeProofSignature(
      contract,
      cctv,
      step1
    );

    await contract.anchorProof(
      caseId,
      1,
      step1.claimHash,
      step1.proofHash,
      step1.result,
      step1.evidenceTimestamp,
      step1.deadline,
      step1.nonce,
      step1.agency,
      sig1
    );

    await expect(
      contract.closeCase(
        caseId,
        "실종자 소재 확인 및 종결"
      )
    ).to.emit(
      contract,
      "CaseClosed"
    );

    const caseInfo = await contract.cases(
      caseId
    );

    expect(caseInfo.status).to.equal(1n);

    expect(caseInfo.closeReason).to.equal(
      "실종자 소재 확인 및 종결"
    );
  });

  
  // ========================================
  // FullProof v1.1 - Claim 원문 고정 테스트
  // ========================================

  it("10. Claim v1을 블록체인에 정상 기록한다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-001")
    );

    const claimHash = ethers.sha256(
      ethers.toUtf8Bytes("실종자와 통화 완료")
    );

    await expect(
      contract.connect(admin).anchorClaim(
        caseId,
        0,
        claimIdHash,
        1,
        claimHash
      )
    ).to.emit(contract, "ClaimAnchored");

    const length = await contract.getClaimHistoryLength(caseId, 0);
    expect(length).to.equal(1n);

    const record = await contract.getClaimRecord(caseId, 0, 0);

    expect(record.claimIdHash).to.equal(claimIdHash);
    expect(record.claimVersion).to.equal(1n);
    expect(record.claimHash).to.equal(claimHash);
    expect(record.recorder).to.equal(admin.address);
    expect(record.recordedAt).to.be.greaterThan(0n);
  });

  it("11. 동일 Claim ID와 버전의 중복 등록을 차단한다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-001")
    );

    const claimHash = ethers.sha256(
      ethers.toUtf8Bytes("실종자와 통화 완료")
    );

    await contract.connect(admin).anchorClaim(
      caseId, 0, claimIdHash, 1, claimHash
    );

    await expect(
      contract.connect(admin).anchorClaim(
        caseId, 0, claimIdHash, 1, claimHash
      )
    ).to.be.revertedWith("Claim version already registered");

    const length = await contract.getClaimHistoryLength(caseId, 0);
    expect(length).to.equal(1n);
  });

  it("12. 권한 없는 지갑의 Claim 등록을 거부한다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-001")
    );

    const claimHash = ethers.sha256(
      ethers.toUtf8Bytes("실종자와 통화 완료")
    );

    await expect(
      contract.connect(outsider).anchorClaim(
        caseId, 0, claimIdHash, 1, claimHash
      )
    ).to.be.revert(ethers);

    const length = await contract.getClaimHistoryLength(caseId, 0);
    expect(length).to.equal(0n);
  });

  it("13. Claim v2 등록 시 v1 이력을 보존한다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-001")
    );

    const claimHashV1 = ethers.sha256(
      ethers.toUtf8Bytes("실종자에게 전화했다")
    );

    const claimHashV2 = ethers.sha256(
      ethers.toUtf8Bytes("실종자와 통화에 성공했다")
    );

    await contract.connect(admin).anchorClaim(
      caseId, 0, claimIdHash, 1, claimHashV1
    );

    await contract.connect(admin).anchorClaim(
      caseId, 0, claimIdHash, 2, claimHashV2
    );

    const length = await contract.getClaimHistoryLength(caseId, 0);
    expect(length).to.equal(2n);

    const recordV1 = await contract.getClaimRecord(caseId, 0, 0);
    const recordV2 = await contract.getClaimRecord(caseId, 0, 1);

    expect(recordV1.claimVersion).to.equal(1n);
    expect(recordV1.claimHash).to.equal(claimHashV1);

    expect(recordV2.claimVersion).to.equal(2n);
    expect(recordV2.claimHash).to.equal(claimHashV2);

    expect(recordV1.claimHash).to.not.equal(recordV2.claimHash);
  });


});