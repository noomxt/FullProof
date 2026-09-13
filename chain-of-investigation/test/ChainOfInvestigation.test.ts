import { expect } from "chai";
import { network } from "hardhat";

describe("ChainOfInvestigation Contract Audit Tests", function () {
  let ethers: any;
  let contract: any, owner: any, addr1: any;
  let caseId: string;

  before(async function () {
    const connection = await network.create();
    ethers = connection.ethers;
  });

  beforeEach(async function () {
    [owner, addr1] = await ethers.getSigners();
    caseId = ethers.keccak256(ethers.toUtf8Bytes("CASE_2026_001"));

    contract = await ethers.deployContract("ChainOfInvestigation");
    await contract.waitForDeployment();
  });

  it("1. 사건 생성 및 앵커링 정상 동작 (VERIFIED)", async function () {
    // 1. 사건 생성
    const tx1 = await contract.createCase(caseId);
    await tx1.wait();

    // 2. 조사 단계 추가
    const tx2 = await contract.addStep(caseId, "STEP 01: 증거 수집");
    await tx2.wait();

    // 3. 앵커링 수행
    const proofHash = ethers.keccak256(ethers.toUtf8Bytes("PROOF_HASH_SAMPLE"));
    const tx3 = await contract.anchorProof(caseId, 0, proofHash, 1);
    const receipt = await tx3.wait();

    expect(receipt.status).to.equal(1);
  });

  it("2. 미등록 지갑의 앵커링 권한 거부 테스트", async function () {
    const tx1 = await contract.createCase(caseId);
    await tx1.wait();

    const tx2 = await contract.addStep(caseId, "STEP 01: 증거 수집");
    await tx2.wait();

    const proofHash = ethers.keccak256(ethers.toUtf8Bytes("PROOF_HASH_SAMPLE"));
    const contractAsAddr1 = contract.connect(addr1);

    let threwError = false;
    try {
      const tx = await contractAsAddr1.anchorProof(caseId, 0, proofHash, 1);
      await tx.wait();
    } catch (error: any) {
      threwError = true;
    }

    expect(threwError).to.be.true;
  });
});