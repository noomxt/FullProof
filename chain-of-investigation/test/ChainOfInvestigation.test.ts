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
    version: "2",
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
  let authorIdHash: string;
  let inputAt: bigint;

  beforeEach(async function () {
    [admin, police, telecom, cctv, outsider] = await ethers.getSigners();

    contract = await ethers.deployContract("ChainOfInvestigation");
    await contract.waitForDeployment();

    caseId = BigInt(
      ethers.keccak256(ethers.toUtf8Bytes("CASE_2026_001"))
    );

    // 테스트용 Claim 원본 작성자 식별자
    authorIdHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-POLICE-AUTHOR-001")
    );

    // 테스트용 원본 입력 시각
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    inputAt = BigInt(latestBlock.timestamp);

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

  it("v1.1: legacy anchorProof is disabled", async function () {
    const claimHash = ethers.keccak256(
      ethers.toUtf8Bytes("LEGACY_CLAIM")
    );
    const proofHash = ethers.keccak256(
      ethers.toUtf8Bytes("LEGACY_PROOF")
    );

    await expect(
      contract.anchorProof(
        caseId,
        0,
        claimHash,
        proofHash,
        STATUS.VERIFIED,
        inputAt,
        inputAt + 3600n,
        0,
        telecom.address,
        "0x"
      )
    ).to.be.revertedWith("Legacy anchorProof disabled");

    const step = await contract.getStepInfo(caseId, 0);
    expect(step[3]).to.equal(STATUS.PENDING);
    expect(step[4]).to.equal(false);
    expect(await contract.agencyNonces(telecom.address)).to.equal(0n);
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

  it("2. Unregistered agency cannot anchor v1.1 Proof", async function () {
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const request = {
      caseId,
      stepId: 0n,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("UNREGISTERED-PROOF-ID")
      ),
      proofVersion: 1n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("UNREGISTERED-PROOF-CONTENT")
      ),
      occurredAt: BigInt(latestBlock.timestamp - 120),
      issuedAt: BigInt(latestBlock.timestamp - 60),
      agency: outsider.address,
      nonce: 0n,
      deadline: BigInt(latestBlock.timestamp + 3600),
    };

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    const signature = await outsider.signTypedData(
      domain,
      types,
      request
    );

    const before = await contract.getAgencyProofHistoryLength(caseId, 0);

    await expect(
      contract.anchorProofAttestation(request, signature)
    ).to.be.revertedWith("Agency is not authorized");

    const after = await contract.getAgencyProofHistoryLength(caseId, 0);

    expect(after).to.equal(before);
    expect(await contract.agencyNonces(outsider.address)).to.equal(0n);
  });

  it("7. v1.1 Proof version history is preserved", async function () {
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    const proofIdHash = ethers.sha256(
      ethers.toUtf8Bytes("VERSIONED-PROOF-001")
    );

    const firstHash = ethers.sha256(
      ethers.toUtf8Bytes("PROOF-CONTENT-V1")
    );

    const secondHash = ethers.sha256(
      ethers.toUtf8Bytes("PROOF-CONTENT-V2")
    );

    const baseRequest = {
      caseId,
      stepId: 0n,
      proofIdHash,
      occurredAt: BigInt(latestBlock.timestamp - 120),
      issuedAt: BigInt(latestBlock.timestamp - 60),
      agency: telecom.address,
      deadline: BigInt(latestBlock.timestamp + 3600),
    };

    const first = {
      ...baseRequest,
      proofVersion: 1n,
      proofHash: firstHash,
      nonce: 0n,
    };

    const firstSignature = await telecom.signTypedData(
      domain, types, first
    );

    await expect(
      contract.anchorProofAttestation(first, firstSignature)
    ).to.emit(contract, "AgencyProofAnchored");

    expect(
      await contract.getAgencyProofHistoryLength(caseId, 0)
    ).to.equal(1n);

    const savedFirst = await contract.getAgencyProofRecord(caseId, 0, 0);

    expect(savedFirst.proofIdHash).to.equal(proofIdHash);
    expect(savedFirst.proofVersion).to.equal(1n);
    expect(savedFirst.proofHash).to.equal(firstHash);

    const second = {
      ...baseRequest,
      proofVersion: 2n,
      proofHash: secondHash,
      nonce: await contract.agencyNonces(telecom.address),
    };

    const secondSignature = await telecom.signTypedData(
      domain, types, second
    );

    await expect(
      contract.anchorProofAttestation(second, secondSignature)
    ).to.emit(contract, "AgencyProofAnchored");

    expect(
      await contract.getAgencyProofHistoryLength(caseId, 0)
    ).to.equal(2n);

    // Older records must remain unchanged.
    const oldRecord = await contract.getAgencyProofRecord(caseId, 0, 0);
    const newRecord = await contract.getAgencyProofRecord(caseId, 0, 1);

    expect(oldRecord.proofIdHash).to.equal(proofIdHash);
    expect(oldRecord.proofVersion).to.equal(1n);
    expect(oldRecord.proofHash).to.equal(firstHash);

    expect(newRecord.proofIdHash).to.equal(proofIdHash);
    expect(newRecord.proofVersion).to.equal(2n);
    expect(newRecord.proofHash).to.equal(secondHash);

    const step = await contract.getStepInfo(caseId, 0);
    expect(step.status).to.equal(BigInt(STATUS.PENDING));
  });

  it("8. Cannot close case without Verification", async function () {
    // No Verification has been recorded for the required steps.
    await expect(
      contract.closeCase(caseId, "?? ??")
    ).to.be.revertedWith("Cannot close: no verification");

    const caseInfo = await contract.cases(caseId);
    expect(caseInfo.status).to.equal(0n);
    expect(caseInfo.closeReason).to.equal("");
  });


  it("9. Proof attestations alone cannot close a case", async function () {
    const networkInfo = await ethers.provider.getNetwork();
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    const agencies = [
      { signer: telecom, stepId: 0n, label: "TELECOM" },
      { signer: cctv, stepId: 1n, label: "CCTV" },
    ];

    for (const agency of agencies) {
      const request = {
        caseId,
        stepId: agency.stepId,
        proofIdHash: ethers.sha256(
          ethers.toUtf8Bytes("PROOF-" + agency.label)
        ),
        proofVersion: 1n,
        proofHash: ethers.sha256(
          ethers.toUtf8Bytes("EVIDENCE-" + agency.label)
        ),
        occurredAt: BigInt(latestBlock.timestamp - 120),
        issuedAt: BigInt(latestBlock.timestamp - 60),
        agency: agency.signer.address,
        nonce: await contract.agencyNonces(agency.signer.address),
        deadline: BigInt(latestBlock.timestamp + 3600),
      };

      const signature = await agency.signer.signTypedData(
        domain,
        types,
        request
      );

      await expect(
        contract.anchorProofAttestation(request, signature)
      ).to.emit(contract, "AgencyProofAnchored");

      const step = await contract.getStepInfo(caseId, agency.stepId);
      expect(step.status).to.equal(BigInt(STATUS.PENDING));
    }

    // Agency Proofs do not replace Verification and administrator approval.
    await expect(
      contract.closeCase(caseId, "Closure without Verification")
    ).to.be.revertedWith("Cannot close: no verification");

    const caseInfo = await contract.cases(caseId);
    expect(caseInfo.status).to.equal(0n);
    expect(caseInfo.closeReason).to.equal("");
  });

  // ========================================
  // FullProof v1.1 Claim tests
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
        claimHash,
        authorIdHash,
        inputAt
      )
    ).to.emit(contract, "ClaimAnchored");

    const length = await contract.getClaimHistoryLength(caseId, 0);
    expect(length).to.equal(1n);

    // 온체인에 저장된 Claim 원본 정보 확인
    const savedClaim = await contract.getClaimRecord(caseId, 0, 0);

    expect(savedClaim.authorIdHash).to.equal(authorIdHash);
    expect(savedClaim.inputAt).to.equal(inputAt);

    // 블록체인 등록자와 원본 작성자 정보는 별도로 보존
    expect(savedClaim.recorder).to.equal(await admin.getAddress());
    expect(savedClaim.recordedAt).to.be.greaterThanOrEqual(inputAt);

    // 작성자 식별자가 비어 있으면 등록 거부
    await expect(
      contract.connect(admin).anchorClaim(
        caseId,
        0,
        ethers.sha256(ethers.toUtf8Bytes("INVALID-CLAIM-001")),
        1,
        ethers.sha256(ethers.toUtf8Bytes("검증용 Claim")),
        ethers.ZeroHash,
        inputAt
      )
    ).to.be.revertedWith("Invalid author ID");

    // 원본 입력 시각이 미래이면 등록 거부
    const currentBlock = await ethers.provider.getBlock("latest");
    if (!currentBlock) throw new Error("Latest block unavailable");

    await expect(
      contract.connect(admin).anchorClaim(
        caseId,
        0,
        ethers.sha256(ethers.toUtf8Bytes("INVALID-CLAIM-002")),
        1,
        ethers.sha256(ethers.toUtf8Bytes("검증용 Claim")),
        authorIdHash,
        BigInt(currentBlock.timestamp + 3600)
      )
    ).to.be.revertedWith("Invalid input time");

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
      caseId, 0, claimIdHash, 1, claimHash, authorIdHash, inputAt
    );

    await expect(
      contract.connect(admin).anchorClaim(
        caseId, 0, claimIdHash, 1, claimHash, authorIdHash, inputAt
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
        caseId, 0, claimIdHash, 1, claimHash, authorIdHash, inputAt
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
      caseId, 0, claimIdHash, 1, claimHashV1, authorIdHash, inputAt
    );

    await contract.connect(admin).anchorClaim(
      caseId, 0, claimIdHash, 2, claimHashV2, authorIdHash, inputAt
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

  it("14. 통신사 공식 서명으로 독립 Proof를 기록한다", async function () {
    const proofIdHash = ethers.sha256(
      ethers.toUtf8Bytes("PROOF-TELECOM-001")
    );

    const proofHash = ethers.sha256(
      ethers.toUtf8Bytes("통신사 원본 통화 기록")
    );

    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const occurredAt = BigInt(latestBlock.timestamp - 120);
    const issuedAt = BigInt(latestBlock.timestamp - 60);
    const deadline = BigInt(latestBlock.timestamp + 3600);

    const nonce = await contract.agencyNonces(telecom.address);

    const request = {
      caseId,
      stepId: 0n,
      proofIdHash,
      proofVersion: 1n,
      proofHash,
      occurredAt,
      issuedAt,
      agency: telecom.address,
      nonce,
      deadline,
    };

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    // 통신사의 공식 지갑으로 Proof에 서명
    const signature = await telecom.signTypedData(
      domain,
      types,
      request
    );

    // 기관 전자서명 검증 후 Proof 기록
    await expect(
      contract.anchorProofAttestation(request, signature)
    ).to.emit(contract, "AgencyProofAnchored");

    // Proof가 등록되어도 최종 검증 판정은 변경되지 않아야 함
    const step = await contract.getStepInfo(caseId, 0);

    expect(step.status).to.equal(BigInt(STATUS.PENDING));

    // 사용된 서명의 nonce는 1 증가해야 함
    expect(
      await contract.agencyNonces(telecom.address)
    ).to.equal(nonce + 1n);
  });

  it("15. 다른 기관이 통신사 Proof에 서명하면 거부한다", async function () {
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const request = {
      caseId,
      stepId: 0n,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("PROOF-TELECOM-002")
      ),
      proofVersion: 1n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("통신사 통화 기록")
      ),
      occurredAt: BigInt(latestBlock.timestamp - 120),
      issuedAt: BigInt(latestBlock.timestamp - 60),
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(latestBlock.timestamp + 3600),
    };

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    // 통신사 Proof를 CCTV 기관 지갑으로 서명
    const fakeSignature = await cctv.signTypedData(
      domain,
      types,
      request
    );

    await expect(
      contract.anchorProofAttestation(request, fakeSignature)
    ).to.be.revertedWith("Invalid electronic signature");

    // 실패한 요청은 nonce를 소비하면 안 됨
    expect(
      await contract.agencyNonces(telecom.address)
    ).to.equal(request.nonce);
  });

  it("16. 동일한 Proof 전자서명의 재사용을 차단한다", async function () {
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const request = {
      caseId,
      stepId: 0n,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("PROOF-REPLAY-001")
      ),
      proofVersion: 1n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("통신사 통화 기록")
      ),
      occurredAt: BigInt(latestBlock.timestamp - 120),
      issuedAt: BigInt(latestBlock.timestamp - 60),
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(latestBlock.timestamp + 3600),
    };

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    const signature = await telecom.signTypedData(
      domain,
      types,
      request
    );

    // 첫 번째 등록: 성공해야 함
    await contract.anchorProofAttestation(request, signature);

    expect(
      await contract.agencyNonces(telecom.address)
    ).to.equal(request.nonce + 1n);

    // 같은 요청과 서명으로 두 번째 등록: 거부해야 함
    await expect(
      contract.anchorProofAttestation(request, signature)
    ).to.be.revert(ethers);

    // 두 번째 실패 후에도 nonce가 그대로 유지되어야 함
    expect(
      await contract.agencyNonces(telecom.address)
    ).to.equal(request.nonce + 1n);
  });

  it("17. 만료된 기관 Proof 전자서명을 거부한다", async function () {
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const request = {
      caseId,
      stepId: 0n,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("PROOF-EXPIRED-001")
      ),
      proofVersion: 1n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("통신사 통화 기록")
      ),
      occurredAt: BigInt(latestBlock.timestamp - 300),
      issuedAt: BigInt(latestBlock.timestamp - 200),
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(latestBlock.timestamp - 10),
    };

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    // 통신사의 공식 지갑으로 서명
    const signature = await telecom.signTypedData(
      domain,
      types,
      request
    );

    // 공식 서명이더라도 만료됐다면 거부
    await expect(
      contract.anchorProofAttestation(request, signature)
    ).to.be.revert(ethers);

    // 실패한 요청으로 nonce가 증가하면 안 됨
    expect(
      await contract.agencyNonces(telecom.address)
    ).to.equal(request.nonce);
  });

  it("18. 새로운 서명이어도 동일 Proof ID 중복 등록을 차단한다", async function () {
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const proofIdHash = ethers.sha256(
      ethers.toUtf8Bytes("PROOF-DUPLICATE-001")
    );

    const proofHash = ethers.sha256(
      ethers.toUtf8Bytes("통신사 원본 통화 기록")
    );

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    // 첫 번째 Proof 등록
    const request1 = {
      caseId,
      stepId: 0n,
      proofIdHash,
      proofVersion: 1n,
      proofHash,
      occurredAt: BigInt(latestBlock.timestamp - 120),
      issuedAt: BigInt(latestBlock.timestamp - 60),
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(latestBlock.timestamp + 3600),
    };

    const signature1 = await telecom.signTypedData(
      domain, types, request1
    );

    await contract.anchorProofAttestation(request1, signature1);

    // 두 번째 요청: nonce와 Proof 내용은 변경, ID는 동일
    const request2 = {
      ...request1,
      proofVersion: 2n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("수정된 통신사 통화 기록")
      ),
      nonce: await contract.agencyNonces(telecom.address),
    };

    const signature2 = await telecom.signTypedData(
      domain, types, request2
    );


    // 동일 Proof ID라도 버전이 다르면 등록 가능
    await expect(
      contract.anchorProofAttestation(request2, signature2)
    ).to.emit(contract, "AgencyProofAnchored");

    // Proof v1과 v2가 모두 저장되었는지 확인
    const count = await contract.getAgencyProofHistoryLength(caseId, 0);
    expect(count).to.equal(2n);

    // 첫 번째 Proof 조회 (v1)
    const record1 = await contract.getAgencyProofRecord(caseId, 0, 0);
    expect(record1.proofIdHash).to.equal(proofIdHash);
    expect(record1.proofVersion).to.equal(1n);

    // 두 번째 Proof 조회 (v2)
    const record2 = await contract.getAgencyProofRecord(caseId, 0, 1);
    expect(record2.proofIdHash).to.equal(proofIdHash);
    expect(record2.proofVersion).to.equal(2n);
    expect(record2.proofHash).to.equal(request2.proofHash);

    // 두 번째 등록이 성공했으므로 nonce도 증가해야 함
    expect(
      await contract.agencyNonces(telecom.address)
    ).to.equal(request2.nonce + 1n);

    // 동일 Proof ID와 v2를 새로운 서명으로 다시 등록하면 거부
    const duplicateRequest = {
      ...request2,
      nonce: await contract.agencyNonces(telecom.address),
    };

    const duplicateSignature = await telecom.signTypedData(
      domain,
      types,
      duplicateRequest
    );

    await expect(
      contract.anchorProofAttestation(
        duplicateRequest,
        duplicateSignature
      )
    ).to.be.revertedWith("Proof already registered");

    // 중복 등록이 거부되면 nonce는 증가하지 않아야 함
    expect(
      await contract.agencyNonces(telecom.address)
    ).to.equal(duplicateRequest.nonce);

  });

  it("19. 기관 Proof 등록 후 온체인 이력을 정확히 조회한다", async function () {
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const proofIdHash = ethers.sha256(
      ethers.toUtf8Bytes("PROOF-HISTORY-001")
    );

    const proofHash = ethers.sha256(
      ethers.toUtf8Bytes("통신사 원본 통화 기록")
    );

    const occurredAt = BigInt(latestBlock.timestamp - 120);
    const issuedAt = BigInt(latestBlock.timestamp - 60);

    const request = {
      caseId,
      stepId: 0n,
      proofIdHash,
      proofVersion: 1n,
      proofHash,
      occurredAt,
      issuedAt,
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(latestBlock.timestamp + 3600),
    };

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    const signature = await telecom.signTypedData(
      domain,
      types,
      request
    );

    // Proof를 블록체인에 등록
    await contract.anchorProofAttestation(request, signature);

    // 이력 개수 조회
    const count = await contract.getAgencyProofHistoryLength(caseId, 0);
    expect(count).to.equal(1n);

    // 등록한 Proof 조회
    const record = await contract.getAgencyProofRecord(caseId, 0, 0);

    expect(record.proofIdHash).to.equal(proofIdHash);
    expect(record.proofHash).to.equal(proofHash);
    expect(record.agency).to.equal(telecom.address);
    expect(record.signer).to.equal(telecom.address);
    expect(record.occurredAt).to.equal(occurredAt);
    expect(record.issuedAt).to.equal(issuedAt);
    expect(record.recordedAt).to.be.greaterThan(0n);

    // Proof 등록이 검증 판정을 변경하지 않는지 다시 확인
    const step = await contract.getStepInfo(caseId, 0);
    expect(step.status).to.equal(BigInt(STATUS.PENDING));
  });

  it("20. 등록되지 않은 계정은 Verification을 기록할 수 없다", async function () {
    const verificationIdHash = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-UNAUTHORIZED-001")
    );

    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-001")
    );

    const claimHash = ethers.sha256(
      ethers.toUtf8Bytes("테스트 Claim 원문")
    );

    const proofRefsHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-PROOF-REFS")
    );

    const policyHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-POLICY")
    );

    const verificationHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-VERIFICATION")
    );


    await expect(
      contract.connect(outsider).anchorVerification(
        caseId,
        0,
        verificationIdHash,
        claimIdHash,
        1,
        claimHash,
        proofRefsHash,
        policyHash,
        verificationHash,
        1
      )
    ).to.be.revertedWith(
      "Not authorized verification recorder"
    );

  });


  it("21. 관리자만 Verification 기록자 권한을 설정할 수 있다", async function () {
    const recorderAddress = await police.getAddress();

    // 권한이 없는 일반 사용자의 등록 시도는 거부
    await expect(
      contract.connect(outsider).setVerificationRecorder(
        recorderAddress,
        true
      )
    ).to.be.revertedWith("Only Admin can do this");

    // 관리자는 시스템 기록자 권한을 부여할 수 있음
    await contract.connect(admin).setVerificationRecorder(
      recorderAddress,
      true
    );

    expect(
      await contract.isVerificationRecorder(recorderAddress)
    ).to.equal(true);

    // 관리자는 권한을 다시 해제할 수도 있음
    await contract.connect(admin).setVerificationRecorder(
      recorderAddress,
      false
    );

    expect(
      await contract.isVerificationRecorder(recorderAddress)
    ).to.equal(false);
  });


  it("22. 등록된 Claim을 참조해 Verification을 기록하고 조회할 수 있다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-VERIFY-001")
    );

    const claimHash = ethers.sha256(
      ethers.toUtf8Bytes("수사관이 통화 연결에 성공했다고 기록했다.")
    );

    const verificationIdHash = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-001")
    );

    // 이번 테스트에서는 형식 확인용 해시 사용
    const proofRefsHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-PROOF-REFS")
    );

    const policyHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-POLICY")
    );

    const verificationHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-VERIFICATION")
    );

    // 1. Claim 원문 해시를 먼저 블록체인에 기록
    await contract.connect(admin).anchorClaim(
      caseId,
      0,
      claimIdHash,
      1,
      claimHash,
      authorIdHash,
      inputAt
    );

    // 2. 관리자 계정이 시스템 기록자 권한 부여
    const recorderAddress = await police.getAddress();

    await contract.connect(admin).setVerificationRecorder(
      recorderAddress,
      true
    );

    // 3. 시스템 기록자가 Verification 결과 등록
    await contract.connect(police).anchorVerification(
      caseId,
      0,
      verificationIdHash,
      claimIdHash,
      1,
      claimHash,
      proofRefsHash,
      policyHash,
      verificationHash,
      2 // CONTRADICTED
    );

    // 4. Verification 이력 개수 확인
    const count = await contract.getVerificationHistoryLength(
      caseId,
      0
    );

    expect(count).to.equal(1n);

    // 5. 온체인에 저장된 Verification 조회
    const record = await contract.getVerificationRecord(
      caseId,
      0,
      0
    );

    expect(record.verificationIdHash).to.equal(verificationIdHash);
    expect(record.claimIdHash).to.equal(claimIdHash);
    expect(record.claimVersion).to.equal(1n);
    expect(record.claimHash).to.equal(claimHash);
    expect(record.proofRefsHash).to.equal(proofRefsHash);
    expect(record.policyHash).to.equal(policyHash);
    expect(record.verificationHash).to.equal(verificationHash);
    expect(record.verdict).to.equal(2n);
    expect(record.recorder).to.equal(recorderAddress);

    // 6. Verification을 등록해도 Step은 자동 검증 완료되지 않음
    const step = await contract.getStepInfo(caseId, 0);

    expect(step[3]).to.equal(0n); // PENDING
    expect(step[4]).to.equal(false); // isCompleted
  });


  it("23. Claim 해시가 다르면 Verification 등록을 거부한다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-CHECK-001")
    );

    const claimHash = ethers.sha256(
      ethers.toUtf8Bytes("원본 Claim")
    );

    const wrongClaimHash = ethers.sha256(
      ethers.toUtf8Bytes("변조된 Claim")
    );

    const verificationIdHash = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-WRONG-CLAIM")
    );

    const proofRefsHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-PROOF-REFS")
    );

    const policyHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-POLICY")
    );

    const verificationHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-VERIFICATION")
    );

    // 실제 Claim 등록
    await contract.connect(admin).anchorClaim(
      caseId,
      0,
      claimIdHash,
      1,
      claimHash,
      authorIdHash,
      inputAt
    );

    // 경찰 테스트 계정에 Verification 기록 권한 부여
    await contract.connect(admin).setVerificationRecorder(
      await police.getAddress(),
      true
    );

    // 존재하는 Claim ID·버전이지만 해시가 다른 경우
    await expect(
      contract.connect(police).anchorVerification(
        caseId,
        0,
        verificationIdHash,
        claimIdHash,
        1,
        wrongClaimHash,
        proofRefsHash,
        policyHash,
        verificationHash,
        1
      )
    ).to.be.revertedWith("Claim reference mismatch");

    // 거부된 거래는 이력에 남지 않아야 함
    expect(
      await contract.getVerificationHistoryLength(caseId, 0)
    ).to.equal(0n);
  });


  it("24. 동일 Verification ID의 중복 등록을 차단한다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-DUPLICATE-001")
    );

    const claimHash = ethers.sha256(
      ethers.toUtf8Bytes("중복 등록 테스트용 Claim 원문")
    );

    const verificationIdHash = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-DUPLICATE-001")
    );

    // 이번 테스트에서는 형식 확인용 해시를 사용
    const proofRefsHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-PROOF-REFS")
    );

    const policyHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-POLICY")
    );

    const verificationHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-VERIFICATION")
    );

    // 1. Claim 등록
    await contract.connect(admin).anchorClaim(
      caseId,
      0,
      claimIdHash,
      1,
      claimHash,
      authorIdHash,
      inputAt
    );

    // 2. 시스템 기록자 권한 부여
    await contract.connect(admin).setVerificationRecorder(
      await police.getAddress(),
      true
    );

    // 3. 첫 번째 Verification 등록 성공
    await contract.connect(police).anchorVerification(
      caseId,
      0,
      verificationIdHash,
      claimIdHash,
      1,
      claimHash,
      proofRefsHash,
      policyHash,
      verificationHash,
      1 // SUPPORTED
    );

    // 4. 똑같은 Verification ID로 다시 등록 시도
    await expect(
      contract.connect(police).anchorVerification(
        caseId,
        0,
        verificationIdHash,
        claimIdHash,
        1,
        claimHash,
        proofRefsHash,
        policyHash,
        verificationHash,
        1
      )
    ).to.be.revertedWith("Verification already registered");

    // 5. 첫 번째 기록만 보존됐는지 확인
    expect(
      await contract.getVerificationHistoryLength(caseId, 0)
    ).to.equal(1n);

    expect(
      await contract.registeredVerificationIds(verificationIdHash)
    ).to.equal(true);
  });


  it("25. 재검증 시 기존 Verification 이력을 보존한다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-REVERIFY-001")
    );

    const claimHashV1 = ethers.sha256(
      ethers.toUtf8Bytes("통화 연결에 성공했다.")
    );

    const claimHashV2 = ethers.sha256(
      ethers.toUtf8Bytes("통화 연결에 실패했다.")
    );

    const verificationIdV1 = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-REVERIFY-001")
    );

    const verificationIdV2 = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-REVERIFY-002")
    );

    // 테스트용 해시: 실제 JCS 결과는 아님
    const proofRefsHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-PROOF-REFS")
    );

    const policyHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-POLICY")
    );

    const verificationHashV1 = ethers.sha256(
      ethers.toUtf8Bytes("VERIFICATION-V1")
    );

    const verificationHashV2 = ethers.sha256(
      ethers.toUtf8Bytes("VERIFICATION-V2")
    );

    // 1. Claim v1 등록
    await contract.connect(admin).anchorClaim(
      caseId, 0, claimIdHash, 1, claimHashV1, authorIdHash, inputAt
    );

    // 2. 시스템 기록자 권한 부여
    await contract.connect(admin).setVerificationRecorder(
      await police.getAddress(),
      true
    );

    // 3. 첫 번째 Verification 등록
    await contract.connect(police).anchorVerification(
      caseId,
      0,
      verificationIdV1,
      claimIdHash,
      1,
      claimHashV1,
      proofRefsHash,
      policyHash,
      verificationHashV1,
      2 // CONTRADICTED
    );

    // 4. Claim v2 등록
    await contract.connect(admin).anchorClaim(
      caseId, 0, claimIdHash, 2, claimHashV2, authorIdHash, inputAt
    );

    // 5. 두 번째 Verification 등록
    await contract.connect(police).anchorVerification(
      caseId,
      0,
      verificationIdV2,
      claimIdHash,
      2,
      claimHashV2,
      proofRefsHash,
      policyHash,
      verificationHashV2,
      1 // SUPPORTED
    );

    // 6. Verification 이력이 2개인지 확인
    const count = await contract.getVerificationHistoryLength(
      caseId, 0
    );

    expect(count).to.equal(2n);

    // 7. 첫 번째 기록이 그대로 남아 있는지 확인
    const first = await contract.getVerificationRecord(
      caseId, 0, 0
    );

    expect(first.verificationIdHash).to.equal(verificationIdV1);
    expect(first.claimVersion).to.equal(1n);
    expect(first.claimHash).to.equal(claimHashV1);
    expect(first.verificationHash).to.equal(verificationHashV1);
    expect(first.verdict).to.equal(2n);

    // 8. 두 번째 기록 확인
    const second = await contract.getVerificationRecord(
      caseId, 0, 1
    );

    expect(second.verificationIdHash).to.equal(verificationIdV2);
    expect(second.claimVersion).to.equal(2n);
    expect(second.claimHash).to.equal(claimHashV2);
    expect(second.verificationHash).to.equal(verificationHashV2);
    expect(second.verdict).to.equal(1n);

    // 9. 기존 Step 상태는 여전히 PENDING
    const step = await contract.getStepInfo(caseId, 0);

    expect(step[3]).to.equal(0n);
    expect(step[4]).to.equal(false);
  });


  it("26. 관리자는 Verification 승인 이력을 기록하고 조회할 수 있다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-REVIEW-001")
    );

    const claimHash = ethers.sha256(
      ethers.toUtf8Bytes("통화 연결에 성공했다.")
    );

    const verificationIdHash = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-REVIEW-001")
    );

    // 단위 테스트용 해시 (실제 JCS 계산 결과는 아님)
    const proofRefsHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-PROOF-REFS")
    );

    const policyHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-POLICY")
    );

    const verificationHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-VERIFICATION")
    );

    // 1. Claim 기록
    await contract.connect(admin).anchorClaim(
      caseId, 0, claimIdHash, 1, claimHash, authorIdHash, inputAt
    );

    // 기관 Proof 등록: 실제 통신사 서명을 검증한다.
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const proofRequest = {
      caseId,
      stepId: 0n,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("PROOF-REVIEW-001")
      ),
      proofVersion: 1n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("통신사 통화 연결 기록")
      ),
      occurredAt: BigInt(latestBlock.timestamp - 120),
      issuedAt: BigInt(latestBlock.timestamp - 60),
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(latestBlock.timestamp + 3600),
    };

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    const proofSignature = await telecom.signTypedData(
      domain,
      types,
      proofRequest
    );

    await contract.anchorProofAttestation(
      proofRequest,
      proofSignature
    );

    // 기관 Proof가 실제 온체인에 등록되었는지 확인
    expect(
      await contract.getAgencyProofHistoryLength(caseId, 0)
    ).to.equal(1n);

    // 2. 시스템 기록자 권한 부여
    await contract.connect(admin).setVerificationRecorder(
      await police.getAddress(),
      true
    );

    // 3. Verification 기록
    await contract.connect(police).anchorVerification(
      caseId,
      0,
      verificationIdHash,
      claimIdHash,
      1,
      claimHash,
      proofRefsHash,
      policyHash,
      verificationHash,
      1 // SUPPORTED
    );

    // 4. 관리자 승인 기록
    await contract.connect(admin).recordVerificationReview(
      caseId,
      0,
      verificationIdHash,
      verificationHash,
      1 // APPROVE
    );

    // 5. 관리자 확인 이력 개수
    const count = await contract.getVerificationReviewHistoryLength(
      caseId, 0
    );

    expect(count).to.equal(1n);

    // 6. 관리자 승인 이력 조회
    const review = await contract.getVerificationReviewRecord(
      caseId, 0, 0
    );

    expect(review.verificationIdHash).to.equal(verificationIdHash);
    expect(review.verificationHash).to.equal(verificationHash);
    expect(review.action).to.equal(1n);
    expect(review.reviewer).to.equal(await admin.getAddress());
    expect(review.reviewedAt).to.be.greaterThan(0n);

    // 7. 기존 Verification 기록이 변경되지 않았는지 확인
    const verification = await contract.getVerificationRecord(
      caseId, 0, 0
    );

    expect(verification.verificationHash).to.equal(verificationHash);
    expect(verification.verdict).to.equal(1n);

  });


  it("27. 관리자가 아닌 계정은 Verification 확인 이력을 기록할 수 없다", async function () {
    const verificationIdHash = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-UNAUTHORIZED-001")
    );

    const verificationHash = ethers.sha256(
      ethers.toUtf8Bytes("UNAUTHORIZED-VERIFICATION-HASH")
    );

    await expect(
      contract.connect(police).recordVerificationReview(
        caseId,
        0,
        verificationIdHash,
        verificationHash,
        1 // APPROVE
      )
    ).to.be.revertedWith(
      "Only Admin can do this"
    );

    expect(
      await contract.getVerificationReviewHistoryLength(caseId, 0)
    ).to.equal(0n);
  });

  it("28. 모든 필수 단계가 승인되면 사건을 종결할 수 있다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-REVIEW-001")
    );

    const claimHash = ethers.sha256(
      ethers.toUtf8Bytes("통화 연결에 성공했다.")
    );

    const verificationIdHash = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-REVIEW-001")
    );

    // 단위 테스트용 해시 (실제 JCS 계산 결과는 아님)
    const proofRefsHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-PROOF-REFS")
    );

    const policyHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-POLICY")
    );

    const verificationHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-VERIFICATION")
    );

    // 1. Claim 기록
    await contract.connect(admin).anchorClaim(
      caseId, 0, claimIdHash, 1, claimHash, authorIdHash, inputAt
    );

    // 기관 Proof 등록: 실제 통신사 서명을 검증한다.
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const proofRequest = {
      caseId,
      stepId: 0n,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("PROOF-REVIEW-001")
      ),
      proofVersion: 1n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("통신사 통화 연결 기록")
      ),
      occurredAt: BigInt(latestBlock.timestamp - 120),
      issuedAt: BigInt(latestBlock.timestamp - 60),
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(latestBlock.timestamp + 3600),
    };

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    const proofSignature = await telecom.signTypedData(
      domain,
      types,
      proofRequest
    );

    await contract.anchorProofAttestation(
      proofRequest,
      proofSignature
    );

    // 기관 Proof가 실제 온체인에 등록되었는지 확인
    expect(
      await contract.getAgencyProofHistoryLength(caseId, 0)
    ).to.equal(1n);

    // 2. 시스템 기록자 권한 부여
    await contract.connect(admin).setVerificationRecorder(
      await police.getAddress(),
      true
    );

    // 3. Verification 기록
    await contract.connect(police).anchorVerification(
      caseId,
      0,
      verificationIdHash,
      claimIdHash,
      1,
      claimHash,
      proofRefsHash,
      policyHash,
      verificationHash,
      1 // SUPPORTED
    );

    // 4. 관리자 승인 기록
    await contract.connect(admin).recordVerificationReview(
      caseId,
      0,
      verificationIdHash,
      verificationHash,
      1 // APPROVE
    );

    // 5. 관리자 확인 이력 개수
    const count = await contract.getVerificationReviewHistoryLength(
      caseId, 0
    );

    expect(count).to.equal(1n);

    // 6. 관리자 승인 이력 조회
    const review = await contract.getVerificationReviewRecord(
      caseId, 0, 0
    );

    expect(review.verificationIdHash).to.equal(verificationIdHash);
    expect(review.verificationHash).to.equal(verificationHash);
    expect(review.action).to.equal(1n);
    expect(review.reviewer).to.equal(await admin.getAddress());
    expect(review.reviewedAt).to.be.greaterThan(0n);

    // 7. 기존 Verification 기록이 변경되지 않았는지 확인
    const verification = await contract.getVerificationRecord(
      caseId, 0, 0
    );

    expect(verification.verificationHash).to.equal(verificationHash);
    expect(verification.verdict).to.equal(1n);

    // 8. 두 번째 필수 단계(stepId=1)의 Claim 등록
    const claimIdHash2 = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-CLOSE-002")
    );

    const claimHash2 = ethers.sha256(
      ethers.toUtf8Bytes("관련 CCTV 확인 완료")
    );

    await contract.connect(admin).anchorClaim(
      caseId, 1, claimIdHash2, 1, claimHash2, authorIdHash, inputAt
    );

    // 9. 두 번째 필수 단계의 Mock 기관 Proof 등록
    const block2 = await ethers.provider.getBlock("latest");

    if (!block2) {
      throw new Error("Latest block unavailable");
    }

    const proofRequest2 = {
      caseId,
      stepId: 1n,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("PROOF-CLOSE-002")
      ),
      proofVersion: 1n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("TEST-STEP-1-PROOF")
      ),
      occurredAt: BigInt(block2.timestamp - 120),
      issuedAt: BigInt(block2.timestamp - 60),
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(block2.timestamp + 3600),
    };

    const proofSignature2 = await telecom.signTypedData(
      domain,
      types,
      proofRequest2
    );

    await contract.anchorProofAttestation(
      proofRequest2,
      proofSignature2
    );

    // 10. 두 번째 필수 단계에 SUPPORTED Verification 기록
    const verificationIdHash2 = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-CLOSE-002")
    );

    const verificationHash2 = ethers.sha256(
      ethers.toUtf8Bytes("TEST-STEP-1-VERIFICATION")
    );

    await contract.connect(police).anchorVerification(
      caseId,
      1,
      verificationIdHash2,
      claimIdHash2,
      1,
      claimHash2,
      ethers.sha256(ethers.toUtf8Bytes("TEST-STEP-1-REFS")),
      policyHash,
      verificationHash2,
      1 // SUPPORTED
    );

    // 11. 두 번째 필수 단계도 관리자 승인
    await contract.connect(admin).recordVerificationReview(
      caseId,
      1,
      verificationIdHash2,
      verificationHash2,
      1 // APPROVE
    );

    // 12. 두 필수 단계가 모두 승인됐으므로 사건 종결
    await expect(
      contract.connect(admin).closeCase(
        caseId,
        "모든 필수 단계 검증 및 관리자 승인 완료"
      )
    ).to.emit(contract, "CaseClosed");

  });

it("29. 관리자 승인 이후 Claim이 변경되면 사건 종결을 차단한다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-REVIEW-001")
    );

    const claimHash = ethers.sha256(
      ethers.toUtf8Bytes("통화 연결에 성공했다.")
    );

    const verificationIdHash = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-REVIEW-001")
    );

    // 단위 테스트용 해시 (실제 JCS 계산 결과는 아님)
    const proofRefsHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-PROOF-REFS")
    );

    const policyHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-POLICY")
    );

    const verificationHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-VERIFICATION")
    );

    // 1. Claim 기록
    await contract.connect(admin).anchorClaim(
      caseId, 0, claimIdHash, 1, claimHash, authorIdHash, inputAt
    );

    // 기관 Proof 등록: 실제 통신사 서명을 검증한다.
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const proofRequest = {
      caseId,
      stepId: 0n,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("PROOF-REVIEW-001")
      ),
      proofVersion: 1n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("통신사 통화 연결 기록")
      ),
      occurredAt: BigInt(latestBlock.timestamp - 120),
      issuedAt: BigInt(latestBlock.timestamp - 60),
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(latestBlock.timestamp + 3600),
    };

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    const proofSignature = await telecom.signTypedData(
      domain,
      types,
      proofRequest
    );

    await contract.anchorProofAttestation(
      proofRequest,
      proofSignature
    );

    // 기관 Proof가 실제 온체인에 등록되었는지 확인
    expect(
      await contract.getAgencyProofHistoryLength(caseId, 0)
    ).to.equal(1n);

    // 2. 시스템 기록자 권한 부여
    await contract.connect(admin).setVerificationRecorder(
      await police.getAddress(),
      true
    );

    // 3. Verification 기록
    await contract.connect(police).anchorVerification(
      caseId,
      0,
      verificationIdHash,
      claimIdHash,
      1,
      claimHash,
      proofRefsHash,
      policyHash,
      verificationHash,
      1 // SUPPORTED
    );

    // 4. 관리자 승인 기록
    await contract.connect(admin).recordVerificationReview(
      caseId,
      0,
      verificationIdHash,
      verificationHash,
      1 // APPROVE
    );

    // 5. 관리자 확인 이력 개수
    const count = await contract.getVerificationReviewHistoryLength(
      caseId, 0
    );

    expect(count).to.equal(1n);

    // 6. 관리자 승인 이력 조회
    const review = await contract.getVerificationReviewRecord(
      caseId, 0, 0
    );

    expect(review.verificationIdHash).to.equal(verificationIdHash);
    expect(review.verificationHash).to.equal(verificationHash);
    expect(review.action).to.equal(1n);
    expect(review.reviewer).to.equal(await admin.getAddress());
    expect(review.reviewedAt).to.be.greaterThan(0n);

    // 7. 기존 Verification 기록이 변경되지 않았는지 확인
    const verification = await contract.getVerificationRecord(
      caseId, 0, 0
    );

    expect(verification.verificationHash).to.equal(verificationHash);
    expect(verification.verdict).to.equal(1n);

    // 8. 두 번째 필수 단계(stepId=1)의 Claim 등록
    const claimIdHash2 = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-CLOSE-002")
    );

    const claimHash2 = ethers.sha256(
      ethers.toUtf8Bytes("관련 CCTV 확인 완료")
    );

    await contract.connect(admin).anchorClaim(
      caseId, 1, claimIdHash2, 1, claimHash2, authorIdHash, inputAt
    );

    // 9. 두 번째 필수 단계의 Mock 기관 Proof 등록
    const block2 = await ethers.provider.getBlock("latest");

    if (!block2) {
      throw new Error("Latest block unavailable");
    }

    const proofRequest2 = {
      caseId,
      stepId: 1n,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("PROOF-CLOSE-002")
      ),
      proofVersion: 1n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("TEST-STEP-1-PROOF")
      ),
      occurredAt: BigInt(block2.timestamp - 120),
      issuedAt: BigInt(block2.timestamp - 60),
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(block2.timestamp + 3600),
    };

    const proofSignature2 = await telecom.signTypedData(
      domain,
      types,
      proofRequest2
    );

    await contract.anchorProofAttestation(
      proofRequest2,
      proofSignature2
    );

    // 10. 두 번째 필수 단계에 SUPPORTED Verification 기록
    const verificationIdHash2 = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-CLOSE-002")
    );

    const verificationHash2 = ethers.sha256(
      ethers.toUtf8Bytes("TEST-STEP-1-VERIFICATION")
    );

    await contract.connect(police).anchorVerification(
      caseId,
      1,
      verificationIdHash2,
      claimIdHash2,
      1,
      claimHash2,
      ethers.sha256(ethers.toUtf8Bytes("TEST-STEP-1-REFS")),
      policyHash,
      verificationHash2,
      1 // SUPPORTED
    );

    // 11. 두 번째 필수 단계도 관리자 승인
    await contract.connect(admin).recordVerificationReview(
      caseId,
      1,
      verificationIdHash2,
      verificationHash2,
      1 // APPROVE
    );


    // 12. 관리자 승인 이후 0번 단계의 Claim을 v2로 변경
    const updatedClaimHash = ethers.sha256(
      ethers.toUtf8Bytes("보호자 연락 결과 수정")
    );

    await contract.connect(admin).anchorClaim(
      caseId,
      0,
      claimIdHash, // 기존 Claim ID 유지
      2,           // Claim 버전 증가
      updatedClaimHash,
      authorIdHash,
      inputAt
    );

    // 13. 이전 승인만으로 사건을 종결할 수 없어야 함
    await expect(
      contract.connect(admin).closeCase(
        caseId,
        "변경된 Claim에 대한 재검증 없이 종결 시도"
      )
    ).to.be.revertedWith("Cannot close: outdated Claim");

  });
it("30. 관리자 승인 이후 Proof가 추가되면 사건 종결을 차단한다", async function () {
    const claimIdHash = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-REVIEW-001")
    );

    const claimHash = ethers.sha256(
      ethers.toUtf8Bytes("통화 연결에 성공했다.")
    );

    const verificationIdHash = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-REVIEW-001")
    );

    // 단위 테스트용 해시 (실제 JCS 계산 결과는 아님)
    const proofRefsHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-PROOF-REFS")
    );

    const policyHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-POLICY")
    );

    const verificationHash = ethers.sha256(
      ethers.toUtf8Bytes("TEST-REVIEW-VERIFICATION")
    );

    // 1. Claim 기록
    await contract.connect(admin).anchorClaim(
      caseId, 0, claimIdHash, 1, claimHash, authorIdHash, inputAt
    );

    // 기관 Proof 등록: 실제 통신사 서명을 검증한다.
    const latestBlock = await ethers.provider.getBlock("latest");

    if (!latestBlock) {
      throw new Error("Latest block unavailable");
    }

    const proofRequest = {
      caseId,
      stepId: 0n,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("PROOF-REVIEW-001")
      ),
      proofVersion: 1n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("통신사 통화 연결 기록")
      ),
      occurredAt: BigInt(latestBlock.timestamp - 120),
      issuedAt: BigInt(latestBlock.timestamp - 60),
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(latestBlock.timestamp + 3600),
    };

    const networkInfo = await ethers.provider.getNetwork();

    const domain = {
      name: "FullProof",
      version: "2",
      chainId: networkInfo.chainId,
      verifyingContract: await contract.getAddress(),
    };

    const types = {
      ProofAttestation: [
        { name: "caseId", type: "uint256" },
        { name: "stepId", type: "uint256" },
        { name: "proofIdHash", type: "bytes32" },
        { name: "proofVersion", type: "uint256" },
        { name: "proofHash", type: "bytes32" },
        { name: "occurredAt", type: "uint64" },
        { name: "issuedAt", type: "uint64" },
        { name: "agency", type: "address" },
        { name: "nonce", type: "uint256" },
        { name: "deadline", type: "uint64" },
      ],
    };

    const proofSignature = await telecom.signTypedData(
      domain,
      types,
      proofRequest
    );

    await contract.anchorProofAttestation(
      proofRequest,
      proofSignature
    );

    // 기관 Proof가 실제 온체인에 등록되었는지 확인
    expect(
      await contract.getAgencyProofHistoryLength(caseId, 0)
    ).to.equal(1n);

    // 2. 시스템 기록자 권한 부여
    await contract.connect(admin).setVerificationRecorder(
      await police.getAddress(),
      true
    );

    // 3. Verification 기록
    await contract.connect(police).anchorVerification(
      caseId,
      0,
      verificationIdHash,
      claimIdHash,
      1,
      claimHash,
      proofRefsHash,
      policyHash,
      verificationHash,
      1 // SUPPORTED
    );

    // 4. 관리자 승인 기록
    await contract.connect(admin).recordVerificationReview(
      caseId,
      0,
      verificationIdHash,
      verificationHash,
      1 // APPROVE
    );

    // 5. 관리자 확인 이력 개수
    const count = await contract.getVerificationReviewHistoryLength(
      caseId, 0
    );

    expect(count).to.equal(1n);

    // 6. 관리자 승인 이력 조회
    const review = await contract.getVerificationReviewRecord(
      caseId, 0, 0
    );

    expect(review.verificationIdHash).to.equal(verificationIdHash);
    expect(review.verificationHash).to.equal(verificationHash);
    expect(review.action).to.equal(1n);
    expect(review.reviewer).to.equal(await admin.getAddress());
    expect(review.reviewedAt).to.be.greaterThan(0n);

    // 7. 기존 Verification 기록이 변경되지 않았는지 확인
    const verification = await contract.getVerificationRecord(
      caseId, 0, 0
    );

    expect(verification.verificationHash).to.equal(verificationHash);
    expect(verification.verdict).to.equal(1n);

    // 8. 두 번째 필수 단계(stepId=1)의 Claim 등록
    const claimIdHash2 = ethers.sha256(
      ethers.toUtf8Bytes("CLAIM-CLOSE-002")
    );

    const claimHash2 = ethers.sha256(
      ethers.toUtf8Bytes("관련 CCTV 확인 완료")
    );

    await contract.connect(admin).anchorClaim(
      caseId, 1, claimIdHash2, 1, claimHash2, authorIdHash, inputAt
    );

    // 9. 두 번째 필수 단계의 Mock 기관 Proof 등록
    const block2 = await ethers.provider.getBlock("latest");

    if (!block2) {
      throw new Error("Latest block unavailable");
    }

    const proofRequest2 = {
      caseId,
      stepId: 1n,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("PROOF-CLOSE-002")
      ),
      proofVersion: 1n,
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("TEST-STEP-1-PROOF")
      ),
      occurredAt: BigInt(block2.timestamp - 120),
      issuedAt: BigInt(block2.timestamp - 60),
      agency: telecom.address,
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(block2.timestamp + 3600),
    };

    const proofSignature2 = await telecom.signTypedData(
      domain,
      types,
      proofRequest2
    );

    await contract.anchorProofAttestation(
      proofRequest2,
      proofSignature2
    );

    // 10. 두 번째 필수 단계에 SUPPORTED Verification 기록
    const verificationIdHash2 = ethers.sha256(
      ethers.toUtf8Bytes("VERIFY-CLOSE-002")
    );

    const verificationHash2 = ethers.sha256(
      ethers.toUtf8Bytes("TEST-STEP-1-VERIFICATION")
    );

    await contract.connect(police).anchorVerification(
      caseId,
      1,
      verificationIdHash2,
      claimIdHash2,
      1,
      claimHash2,
      ethers.sha256(ethers.toUtf8Bytes("TEST-STEP-1-REFS")),
      policyHash,
      verificationHash2,
      1 // SUPPORTED
    );

    // 11. 두 번째 필수 단계도 관리자 승인
    await contract.connect(admin).recordVerificationReview(
      caseId,
      1,
      verificationIdHash2,
      verificationHash2,
      1 // APPROVE
    );



    // 12. 관리자 승인 이후 새로운 기관 Proof 등록
    const block3 = await ethers.provider.getBlock("latest");

    if (!block3) {
      throw new Error("Latest block unavailable");
    }

    const updatedProofRequest = {
      ...proofRequest,
      proofIdHash: ethers.sha256(
        ethers.toUtf8Bytes("PROOF-AFTER-APPROVAL-001")
      ),
      proofHash: ethers.sha256(
        ethers.toUtf8Bytes("관리자 승인 이후 추가된 통신사 자료")
      ),
      occurredAt: BigInt(block3.timestamp - 120),
      issuedAt: BigInt(block3.timestamp - 60),
      nonce: await contract.agencyNonces(telecom.address),
      deadline: BigInt(block3.timestamp + 3600),
    };

    const updatedProofSignature = await telecom.signTypedData(
      domain,
      types,
      updatedProofRequest
    );

    await contract.anchorProofAttestation(
      updatedProofRequest,
      updatedProofSignature
    );

    // 13. 기존 승인으로 사건 종결을 시도하면 차단되어야 함
    await expect(
      contract.connect(admin).closeCase(
        caseId,
        "Proof 추가 이후 재검증 없이 종결 시도"
      )
    ).to.be.revertedWith("Cannot close: Proof history changed");

  });
});
