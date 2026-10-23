// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/**
 * FullProof - Chain of Investigation
 *
 * 목적
 * - 실종수사/공공수사 사건의 Claim과 원천기관 Proof를 연결
 * - 기관 전자서명(EIP-712) 검증
 * - 검증 결과와 해시를 온체인에 앵커링
 * - 기존 기록을 덮어쓰지 않고 Proof history를 누적하여 감사 추적성 확보
 * - 원본 증거/개인정보는 온체인에 저장하지 않음
 */
contract ChainOfInvestigation is EIP712 {
    using ECDSA for bytes32;

    // -----------------------------
    // Types
    // -----------------------------

    enum AgencyType {
        NONE,
        POLICE,
        TELECOM,
        CCTV
    }

    enum VerificationStatus {
        PENDING,
        VERIFIED,
        MISMATCH,
        EXPIRING_SOON
    }

     // FullProof v1.1: AI + Rule Engine 최종 검증 판정
    enum VerificationVerdict {
        NONE,
        SUPPORTED,
        CONTRADICTED,
        INSUFFICIENT
    }
    
    // FullProof v1.1: 관리자 확인 조치 유형
    enum VerificationReviewAction {
        NONE,
        APPROVE,
        CONFIRM,
        REQUEST_CHANGES
    }

    enum CaseStatus {
        OPEN,
        CLOSED
    }

    /**
     * 기관 등록 정보
     * agency = 기관 식별용 지갑
     * signer = 실제 전자서명에 사용하는 승인된 서명자 지갑
     */
    struct AgencyInfo {
        AgencyType agencyType;
        bool active;
        address signer;
    }

    struct Step {
        string stepName;
        bool isRequired;
        VerificationStatus status;
        bytes32 claimHash;
        bytes32 proofHash;
        bool isCompleted;
    }

    struct CaseInfo {
        uint256 caseId;
        CaseStatus status;
        uint256 stepCount;
        bool exists;
        string closeReason;
        uint64 createdAt;
        uint64 closedAt;
        address creator;
        address closer;
    }

    /**
     * 하나의 Step에서 발생한 개별 Proof 검증 이력.
     * 이전 기록을 삭제/수정하지 않고 계속 누적한다.
     */
    struct ProofRecord {
        uint256 proofId;
        address agency;
        address signer;
        bytes32 claimHash;
        bytes32 proofHash;
        VerificationStatus status;
        uint64 evidenceTimestamp;
        uint64 recordedAt;
        bytes32 signatureDigest;
    }

    /**
     * EIP-712 서명 대상 데이터.
     * 기관이 서명한 뒤, backend/relayer가 이 서명과 함께 anchorProof를 호출한다.
     */
    struct ProofRequest {
        uint256 caseId;
        uint256 stepId;
        bytes32 claimHash;
        bytes32 proofHash;
        VerificationStatus result;
        uint64 evidenceTimestamp;
        uint256 nonce;
        uint64 deadline;
        address agency;
    }

    bytes32 private constant PROOF_TYPEHASH = keccak256(
        "Proof(uint256 caseId,uint256 stepId,bytes32 claimHash,bytes32 proofHash,uint8 result,uint64 evidenceTimestamp,uint256 nonce,uint64 deadline,address agency)"
    );

    // FullProof v1.1: 기관이 자신의 Proof에 대해서만 서명
    struct ProofAttestation {
         uint256 caseId;
        uint256 stepId;
        bytes32 proofIdHash;
        uint256 proofVersion;
        bytes32 proofHash;
        uint64 occurredAt;
        uint64 issuedAt;
        address agency;
        uint256 nonce;
        uint64 deadline;
    }


    // FullProof v1.1 - 기관이 독립적으로 등록한 Proof 기록
    struct AgencyProofRecord {
        bytes32 proofIdHash;
        uint256 proofVersion;
        bytes32 proofHash;
        address agency;
        address signer;
        uint64 occurredAt;
        uint64 issuedAt;
        uint64 recordedAt;
        bytes32 signatureDigest;
    }
    // FullProof v1.1: AI + Rule Engine 검증 결과 이력
    struct VerificationRecord {
        bytes32 verificationIdHash;

        // 검증 대상 Claim의 ID, 버전, 원문 해시
        bytes32 claimIdHash;
        uint256 claimVersion;
        bytes32 claimHash;

        // 검증에 사용된 Proof 목록 및 정책 해시
        bytes32 proofRefsHash;
        bytes32 policyHash;

        // Verification 기록 당시 등록된 기관 Proof 이력 개수
        uint256 proofHistoryCount;

        // Verification 전체 결과 해시
        bytes32 verificationHash;

        // 최종 판정
        VerificationVerdict verdict;

        // 블록체인 기록 정보
        uint64 recordedAt;
        address recorder;
    }

    
    // FullProof v1.1: Verification 관리자 확인 이력
    struct VerificationReviewRecord {
        bytes32 verificationIdHash;
        bytes32 verificationHash;
        VerificationReviewAction action;
        address reviewer;
        uint64 reviewedAt;
    }
    
    bytes32 private constant PROOF_ATTESTATION_TYPEHASH = keccak256(
        "ProofAttestation(uint256 caseId,uint256 stepId,bytes32 proofIdHash,uint256 proofVersion,bytes32 proofHash,uint64 occurredAt,uint64 issuedAt,address agency,uint256 nonce,uint64 deadline)"
    );


    // -----------------------------
    // Storage
    // -----------------------------

    address public admin;

    // FullProof v1.1: Verification 결과 기록 권한
    mapping(address => bool) public isVerificationRecorder;

    // 기존 코드와의 호환성을 위해 유지
    mapping(address => bool) public isPolice;
    mapping(address => bool) public isTelecom;
    mapping(address => bool) public isCCTV;

    mapping(address => AgencyInfo) public agencies;
    mapping(address => uint256) public agencyNonces;

    mapping(uint256 => address) public caseFamily;
    mapping(uint256 => CaseInfo) public cases;
    mapping(uint256 => mapping(uint256 => Step)) public caseSteps;

    // Step별 Proof history. 원본 이력은 지우지 않는다.
    mapping(uint256 => mapping(uint256 => ProofRecord[])) private proofHistory;

    // FullProof v1.1 - 기존 검증 이력과 분리된 기관 Proof 이력
    mapping(uint256 => mapping(uint256 => AgencyProofRecord[]))
        private agencyProofHistory;

    // 동일 사건·단계 내 동일 Proof ID의 재등록 방지
    mapping(bytes32 => bool) public registeredAgencyProofs;

    mapping(uint256 => mapping(uint256 => uint256)) public latestProofId;

    uint256 public nextProofId = 1;

    // Claim 원문 고정 이력
    struct ClaimRecord {
        bytes32 claimIdHash;
        uint256 claimVersion;
        bytes32 claimHash;
        bytes32 authorIdHash;
        uint64 inputAt;
        uint64 recordedAt;
        address recorder;
    }
    mapping(uint256 => mapping(uint256 => ClaimRecord[]))
        private claimHistory;

    // 같은 Claim ID와 버전의 중복 등록 방지
    mapping(bytes32 => bool) public registeredClaimVersions;

    // FullProof v1.1: 사건별·단계별 Verification 이력
    mapping(uint256 => mapping(uint256 => VerificationRecord[]))
        private verificationHistory;
    // 동일 Verification ID 중복 기록 방지
    mapping(bytes32 => bool) public registeredVerificationIds;
    
    // FullProof v1.1: 사건·단계별 관리자 확인 이력
    mapping(uint256 => mapping(uint256 => VerificationReviewRecord[]))
        private verificationReviewHistory;

    // -----------------------------
    // Events
    // -----------------------------

    event AgencyRegistered(
        address indexed agency,
        AgencyType indexed agencyType,
        address indexed signer
    );

    event AgencyStatusChanged(address indexed agency, bool active);

    // Verification 기록자 권한 변경 이력
    event VerificationRecorderUpdated(
        address indexed recorder,
        bool authorized
    );
    event AgencySignerChanged(address indexed agency, address indexed oldSigner, address indexed newSigner);

    event CaseCreated(uint256 indexed caseId, address indexed creator, uint256 createdAt);

    event StepAdded(
        uint256 indexed caseId,
        uint256 indexed stepId,
        string stepName,
        bool isRequired
    );

    event ProofAnchored(
        uint256 indexed caseId,
        uint256 indexed stepId,
        uint256 indexed proofId,
        address agency,
        address signer,
        bytes32 claimHash,
        bytes32 proofHash,
        VerificationStatus status,
        uint64 evidenceTimestamp,
        bytes32 signatureDigest
    );


    event AgencyProofAnchored(
        uint256 indexed caseId,
        uint256 indexed stepId,
        bytes32 indexed proofIdHash,
        uint256 proofVersion,
        bytes32 proofHash,
        address agency,
        address signer,
        uint64 occurredAt,
        uint64 issuedAt,
        uint64 recordedAt,
        bytes32 signatureDigest
    );


    event CaseClosed(
        uint256 indexed caseId,
        string reason,
        address indexed closer,
        uint256 closedAt
    );


    
    event ClaimAnchored(
        uint256 indexed caseId,
        uint256 indexed stepId,
        bytes32 indexed claimIdHash,
        uint256 claimVersion,
        bytes32 claimHash,
        bytes32 authorIdHash,
        uint64 inputAt,
        address recorder,
        uint64 recordedAt
    );


    // FullProof v1.1: Verification 결과 온체인 기록 이벤트
    event VerificationAnchored(
        uint256 indexed caseId,
        uint256 indexed stepId,
        bytes32 indexed verificationIdHash,
        bytes32 verificationHash,
        VerificationVerdict verdict,
        address recorder,
        uint64 recordedAt
    );
    
    // FullProof v1.1: 관리자 확인 조치 기록 이벤트
    event VerificationReviewAnchored(
        uint256 indexed caseId,
        uint256 indexed stepId,
        bytes32 indexed verificationIdHash,
        bytes32 verificationHash,
        VerificationReviewAction action,
        address reviewer,
        uint64 reviewedAt
    );

    // -----------------------------
    // Modifiers
    // -----------------------------

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only Admin can do this");
        _;
    }

    // Verification 결과는 허용된 시스템 기록자만 등록
    modifier onlyVerificationRecorder() {
        require(
            isVerificationRecorder[msg.sender],
            "Not authorized verification recorder"
        );
        _;
    }


    modifier onlyPoliceOrAdmin() {
        require(msg.sender == admin || isPolice[msg.sender], "Only Police/Admin can do this");
        _;
    }

    modifier caseExists(uint256 caseId) {
        require(cases[caseId].exists, "Case does not exist");
        _;
    }

    modifier onlyOpen(uint256 caseId) {
        require(cases[caseId].exists, "Case does not exist");
        require(cases[caseId].status == CaseStatus.OPEN, "Case is already CLOSED");
        _;
    }

    // -----------------------------
    // Constructor
    // -----------------------------

    constructor() EIP712("FullProof", "2") {
        admin = msg.sender;

        // 배포자를 관리자 + 경찰 기관 지갑으로 등록
        isPolice[msg.sender] = true;
        agencies[msg.sender] = AgencyInfo({
            agencyType: AgencyType.POLICE,
            active: true,
            signer: msg.sender
        });

        emit AgencyRegistered(msg.sender, AgencyType.POLICE, msg.sender);
    }

    // 관리자만 Verification 기록자를 등록하거나 해제할 수 있음
    function setVerificationRecorder(
        address recorder,
        bool authorized
    ) external onlyAdmin {
        require(recorder != address(0), "Invalid recorder");

        isVerificationRecorder[recorder] = authorized;

        emit VerificationRecorderUpdated(recorder, authorized);
    }


    // -----------------------------
    // Agency management
    // -----------------------------

    function registerAgency(
        address agency,
        AgencyType agencyType,
        address signer
    ) external onlyAdmin {
        require(agency != address(0), "Invalid agency");
        require(agencyType != AgencyType.NONE, "Invalid agency type");

        if (signer == address(0)) {
            signer = agency;
        }

        // role compatibility mappings reset
        isPolice[agency] = false;
        isTelecom[agency] = false;
        isCCTV[agency] = false;

        if (agencyType == AgencyType.POLICE) {
            isPolice[agency] = true;
        } else if (agencyType == AgencyType.TELECOM) {
            isTelecom[agency] = true;
        } else if (agencyType == AgencyType.CCTV) {
            isCCTV[agency] = true;
        }

        agencies[agency] = AgencyInfo({
            agencyType: agencyType,
            active: true,
            signer: signer
        });

        emit AgencyRegistered(agency, agencyType, signer);
    }

    function setAgencyActive(address agency, bool active) external onlyAdmin {
        require(agencies[agency].agencyType != AgencyType.NONE, "Agency not registered");
        agencies[agency].active = active;
        emit AgencyStatusChanged(agency, active);
    }

    function setAgencySigner(address agency, address newSigner) external onlyAdmin {
        require(agencies[agency].agencyType != AgencyType.NONE, "Agency not registered");
        require(newSigner != address(0), "Invalid signer");

        address oldSigner = agencies[agency].signer;
        agencies[agency].signer = newSigner;

        emit AgencySignerChanged(agency, oldSigner, newSigner);
    }

    function isAuthorizedAgency(address agency) public view returns (bool) {
        return agency == admin || (agencies[agency].active && agencies[agency].agencyType != AgencyType.NONE);
    }

    function getAgencyInfo(address agency)
        external
        view
        returns (AgencyType agencyType, bool active, address signer, uint256 nonce)
    {
        AgencyInfo memory info = agencies[agency];
        return (info.agencyType, info.active, info.signer, agencyNonces[agency]);
    }

    // -----------------------------
    // Case management
    // -----------------------------

    function registerFamilyWallet(uint256 caseId, address familyWallet)
        external
        onlyOpen(caseId)
        onlyPoliceOrAdmin
    {
        caseFamily[caseId] = familyWallet;
    }

    function createCase(uint256 caseId) external onlyPoliceOrAdmin {
        require(caseId != 0, "Invalid case id");
        require(!cases[caseId].exists, "Case already exists");

        cases[caseId] = CaseInfo({
            caseId: caseId,
            status: CaseStatus.OPEN,
            stepCount: 0,
            exists: true,
            closeReason: "",
            createdAt: uint64(block.timestamp),
            closedAt: 0,
            creator: msg.sender,
            closer: address(0)
        });

        emit CaseCreated(caseId, msg.sender, block.timestamp);
    }

    function addStep(
        uint256 caseId,
        string memory stepName,
        bool isRequired
    ) external onlyOpen(caseId) onlyPoliceOrAdmin {
        require(bytes(stepName).length > 0, "Step name is empty");

        uint256 stepIndex = cases[caseId].stepCount;

        caseSteps[caseId][stepIndex] = Step({
            stepName: stepName,
            isRequired: isRequired,
            status: VerificationStatus.PENDING,
            claimHash: bytes32(0),
            proofHash: bytes32(0),
            isCompleted: false
        });

        cases[caseId].stepCount++;

        emit StepAdded(caseId, stepIndex, stepName, isRequired);
    }


    
    function anchorClaim(
        uint256 caseId,
        uint256 stepId,
        bytes32 claimIdHash,
        uint256 claimVersion,
        bytes32 claimHash,
        bytes32 authorIdHash,
        uint64 inputAt
    )
        external
        onlyOpen(caseId)
        onlyPoliceOrAdmin
    {
        require(
            stepId < cases[caseId].stepCount,
            "Invalid step"
        );

        require(
            claimIdHash != bytes32(0),
            "Invalid claim ID"
        );

        require(
            claimHash != bytes32(0),
            "Invalid claim hash"
        );
        
        // 원본 작성자 식별자 필수
        require(
            authorIdHash != bytes32(0),
            "Invalid author ID"
        );

        // 원본 입력 시각은 0이거나 미래일 수 없음
        require(
            inputAt > 0 && inputAt <= block.timestamp,
            "Invalid input time"
        );

        require(
            claimVersion > 0,
            "Invalid claim version"
        );

        bytes32 versionKey = keccak256(
            abi.encode(
                caseId,
                stepId,
                claimIdHash,
                claimVersion
            )
        );

        require(
            !registeredClaimVersions[versionKey],
            "Claim version already registered"
        );

        registeredClaimVersions[versionKey] = true;

        claimHistory[caseId][stepId].push(
            ClaimRecord({
                claimIdHash: claimIdHash,
                claimVersion: claimVersion,
                claimHash: claimHash,
                authorIdHash: authorIdHash,
                inputAt: inputAt,
                recordedAt: uint64(block.timestamp),
                recorder: msg.sender
            })
        );

        emit ClaimAnchored(
            caseId,
            stepId,
            claimIdHash,
            claimVersion,
            claimHash,
            authorIdHash,
            inputAt,
            msg.sender,
            uint64(block.timestamp)
        );
    }


    function getClaimHistoryLength(
        uint256 caseId,
        uint256 stepId
    ) external view returns (uint256) {
        return claimHistory[caseId][stepId].length;
    }

    function getClaimRecord(
        uint256 caseId,
        uint256 stepId,
        uint256 index
    ) external view returns (ClaimRecord memory) {
        require(
            index < claimHistory[caseId][stepId].length,
            "Invalid claim index"
        );

        return claimHistory[caseId][stepId][index];
    }
    
    // FullProof v1.1: 사건·단계별 가장 최근에 등록된 Claim 조회
    function getLatestClaim(
        uint256 caseId,
        uint256 stepId
    ) external view caseExists(caseId) returns (ClaimRecord memory) {
        require(
            stepId < cases[caseId].stepCount,
            "Invalid step"
        );

        uint256 count = claimHistory[caseId][stepId].length;

        require(
            count > 0,
            "No claim record"
        );

        return claimHistory[caseId][stepId][count - 1];
    }
    
    // FullProof v1.1: 최신 Verification이 최신 Claim을 참조하는지 검사
    function isLatestClaimVerified(
        uint256 caseId,
        uint256 stepId
    ) public view caseExists(caseId) returns (bool) {
        require(
            stepId < cases[caseId].stepCount,
            "Invalid step"
        );

        uint256 claimCount = claimHistory[caseId][stepId].length;
        uint256 verificationCount =
            verificationHistory[caseId][stepId].length;

        // Claim 또는 Verification이 없으면 검증 불충분
        if (claimCount == 0 || verificationCount == 0) {
            return false;
        }

        ClaimRecord storage latestClaim =
            claimHistory[caseId][stepId][claimCount - 1];

        VerificationRecord storage latestVerification =
            verificationHistory[caseId][stepId][verificationCount - 1];

        return (
            latestClaim.claimIdHash == latestVerification.claimIdHash &&
            latestClaim.claimVersion == latestVerification.claimVersion &&
            latestClaim.claimHash == latestVerification.claimHash
        );
    }
    
    // FullProof v1.1: 최신 Verification 이후 Proof 추가 여부 확인
    function isProofHistoryUnchanged(
        uint256 caseId,
        uint256 stepId
    ) public view caseExists(caseId) returns (bool) {
        require(
            stepId < cases[caseId].stepCount,
            "Invalid step"
        );

        uint256 verificationCount =
            verificationHistory[caseId][stepId].length;

        // Verification 기록이 없으면 확인 불가능
        if (verificationCount == 0) {
            return false;
        }

        VerificationRecord storage latestVerification =
            verificationHistory[caseId][stepId][verificationCount - 1];

        uint256 currentProofCount =
            agencyProofHistory[caseId][stepId].length;

        return (
            latestVerification.proofHistoryCount == currentProofCount
        );
    }
    
    // 최신 Verification에 대한 관리자 승인 여부 확인
    function isLatestVerificationApproved(
        uint256 caseId,
        uint256 stepId
    ) public view caseExists(caseId) returns (bool) {
        require(
            stepId < cases[caseId].stepCount,
            "Invalid step"
        );

        uint256 verificationCount =
            verificationHistory[caseId][stepId].length;

        if (verificationCount == 0) {
            return false;
        }

        VerificationRecord storage latestVerification =
            verificationHistory[caseId][stepId][verificationCount - 1];

        VerificationReviewRecord[] storage reviews =
            verificationReviewHistory[caseId][stepId];

        // 가장 최근 관리자 검토 조치를 기준으로 판단
        if (reviews.length == 0) {
            return false;
        }

        VerificationReviewRecord storage latestReview =
            reviews[reviews.length - 1];

        return (
            latestReview.verificationIdHash ==
                latestVerification.verificationIdHash &&
            latestReview.verificationHash ==
                latestVerification.verificationHash &&
            latestReview.action == VerificationReviewAction.APPROVE
        );
    }

    // FullProof v1.1: 등록된 Claim ID·버전·해시 일치 확인
    function isRegisteredClaim(
        uint256 caseId,
        uint256 stepId,
        bytes32 claimIdHash,
        uint256 claimVersion,
        bytes32 claimHash
    ) public view returns (bool) {

        if (!cases[caseId].exists) {
            return false;
        }

        if (stepId >= cases[caseId].stepCount) {
            return false;
        }

        ClaimRecord[] storage records = claimHistory[caseId][stepId];

        for (uint256 i = 0; i < records.length; i++) {
            if (
                records[i].claimIdHash == claimIdHash &&
                records[i].claimVersion == claimVersion &&
                records[i].claimHash == claimHash
            ) {
                return true;
            }
        }

        return false;
    }

    // FullProof v1.1: 최종 Verification 결과 독립 기록
    function anchorVerification(
        uint256 caseId,
        uint256 stepId,
        bytes32 verificationIdHash,
        bytes32 claimIdHash,
        uint256 claimVersion,
        bytes32 claimHash,
        bytes32 proofRefsHash,
        bytes32 policyHash,
        bytes32 verificationHash,
        VerificationVerdict verdict
    )
        external
        onlyOpen(caseId)
        onlyVerificationRecorder
    {
        require(
            stepId < cases[caseId].stepCount,
            "Invalid step"
        );

        require(
            verificationIdHash != bytes32(0),
            "Invalid verification ID"
        );

        require(
            verificationHash != bytes32(0),
            "Invalid verification hash"
        );

        require(
            proofRefsHash != bytes32(0),
            "Invalid proof refs hash"
        );
        
        require(
            policyHash != bytes32(0),
            "Invalid policy hash"
        );

        require(
            verdict != VerificationVerdict.NONE,
            "Invalid final verdict"
        );

        require(
            isRegisteredClaim(
                caseId,
                stepId,
                claimIdHash,
                claimVersion,
                claimHash
            ),
            "Claim reference mismatch"
        );

        require(
            !registeredVerificationIds[verificationIdHash],
            "Verification already registered"
        );

        registeredVerificationIds[verificationIdHash] = true;

        verificationHistory[caseId][stepId].push(
            VerificationRecord({
                verificationIdHash: verificationIdHash,
                claimIdHash: claimIdHash,
                claimVersion: claimVersion,
                claimHash: claimHash,
                proofRefsHash: proofRefsHash,
                policyHash: policyHash,
                proofHistoryCount: agencyProofHistory[caseId][stepId].length,
                verificationHash: verificationHash,
                verdict: verdict,
                recordedAt: uint64(block.timestamp),
                recorder: msg.sender
            })
        );

        emit VerificationAnchored(
            caseId,
            stepId,
            verificationIdHash,
            verificationHash,
            verdict,
            msg.sender,
            uint64(block.timestamp)
        );
    }

    // FullProof v1.1: 해당 사건·단계의 Verification 기록 개수
    function getVerificationHistoryLength(
        uint256 caseId,
        uint256 stepId
    ) external view returns (uint256) {
        return verificationHistory[caseId][stepId].length;
    }

    // FullProof v1.1: 특정 Verification 기록 조회
    function getVerificationRecord(
        uint256 caseId,
        uint256 stepId,
        uint256 index
    ) external view returns (VerificationRecord memory) {
        require(
            index < verificationHistory[caseId][stepId].length,
            "Invalid verification index"
        );

        return verificationHistory[caseId][stepId][index];
    }
    
    // FullProof v1.1: 사건·단계별 최신 Verification 조회
    function getLatestVerification(
        uint256 caseId,
        uint256 stepId
    ) external view returns (VerificationRecord memory) {
        require(
            stepId < cases[caseId].stepCount,
            "Invalid step"
        );

        uint256 count = verificationHistory[caseId][stepId].length;

        require(
            count > 0,
            "No verification record"
        );

        return verificationHistory[caseId][stepId][count - 1];
    }
    
    // FullProof v1.1: Verification ID와 결과 해시의 등록 여부 확인
    function isRegisteredVerification(
        uint256 caseId,
        uint256 stepId,
        bytes32 verificationIdHash,
        bytes32 verificationHash
    ) public view returns (bool) {
        VerificationRecord[] storage records =
            verificationHistory[caseId][stepId];

        for (uint256 i = 0; i < records.length; i++) {
            if (
                records[i].verificationIdHash == verificationIdHash &&
                records[i].verificationHash == verificationHash
            ) {
                return true;
            }
        }

        return false;
    }
    
    // FullProof v1.1: Verification 관리자 확인 이력 기록
    function recordVerificationReview(
        uint256 caseId,
        uint256 stepId,
        bytes32 verificationIdHash,
        bytes32 verificationHash,
        VerificationReviewAction action
    )
        external
        onlyOpen(caseId)
        onlyAdmin
    {
        require(
            action != VerificationReviewAction.NONE,
            "Invalid review action"
        );

        require(
            isRegisteredVerification(
                caseId,
                stepId,
                verificationIdHash,
                verificationHash
            ),
            "Verification reference mismatch"
        );
        
        // 관리자 검토는 해당 단계의 최신 Verification만 허용
        uint256 verificationCount =
            verificationHistory[caseId][stepId].length;

        require(
            verificationCount > 0,
            "No verification record"
        );

        VerificationRecord storage latestVerification =
            verificationHistory[caseId][stepId][verificationCount - 1];

        require(
            latestVerification.verificationIdHash == verificationIdHash &&
            latestVerification.verificationHash == verificationHash,
            "Review must reference latest verification"
        );
        
        // 최종 승인 시에는 최신 Claim과 Proof 기준의 검증이어야 함
        if (action == VerificationReviewAction.APPROVE) {
            require(
                isLatestClaimVerified(caseId, stepId),
                "Cannot approve: outdated Claim"
            );

            require(
                isProofHistoryUnchanged(caseId, stepId),
                "Cannot approve: Proof history changed"
            );

            require(
                latestVerification.verdict == VerificationVerdict.SUPPORTED,
                "Cannot approve: verification not supported"
            );

            require(
                agencyProofHistory[caseId][stepId].length > 0,
                "Cannot approve: no agency Proof"
            );
        }

        uint64 reviewedAt = uint64(block.timestamp);

        verificationReviewHistory[caseId][stepId].push(
            VerificationReviewRecord({
                verificationIdHash: verificationIdHash,
                verificationHash: verificationHash,
                action: action,
                reviewer: msg.sender,
                reviewedAt: reviewedAt
            })
        );

        emit VerificationReviewAnchored(
            caseId,
            stepId,
            verificationIdHash,
            verificationHash,
            action,
            msg.sender,
            reviewedAt
        );
    }
    
    // FullProof v1.1: 관리자 확인 이력 개수 조회
    function getVerificationReviewHistoryLength(
        uint256 caseId,
        uint256 stepId
    ) external view returns (uint256) {
        return verificationReviewHistory[caseId][stepId].length;
    }

    // FullProof v1.1: 관리자 확인 이력 개별 조회
    function getVerificationReviewRecord(
        uint256 caseId,
        uint256 stepId,
        uint256 index
    ) external view returns (VerificationReviewRecord memory) {
        require(
            index < verificationReviewHistory[caseId][stepId].length,
            "Invalid review index"
        );

        return verificationReviewHistory[caseId][stepId][index];
    }

    // -----------------------------
    // EIP-712 signature verification
    // -----------------------------


    // FullProof v1.1 - 기관 독립 Proof EIP-712 해시
    function getProofAttestationTypedDataHash(
        ProofAttestation memory request
    ) public view returns (bytes32) {

        bytes32 structHash = keccak256(
            abi.encode(
                PROOF_ATTESTATION_TYPEHASH,
                request.caseId,
                request.stepId,
                request.proofIdHash,
                request.proofVersion,
                request.proofHash,
                request.occurredAt,
                request.issuedAt,
                request.agency,
                request.nonce,
                request.deadline
            )
        );

        return _hashTypedDataV4(structHash);
    }

    // FullProof v1.1 - Proof 전자서명에서 서명자 주소 복구
    function recoverProofAttestationSigner(
        ProofAttestation calldata request,
        bytes calldata signature
    ) public view returns (address) {

        bytes32 digest = getProofAttestationTypedDataHash(
            request
        );

        return ECDSA.recover(digest, signature);
    }


    function getProofTypedDataHash(ProofRequest memory request) public view returns (bytes32) {
        bytes32 structHash = keccak256(
            abi.encode(
                PROOF_TYPEHASH,
                request.caseId,
                request.stepId,
                request.claimHash,
                request.proofHash,
                uint8(request.result),
                request.evidenceTimestamp,
                request.nonce,
                request.deadline,
                request.agency
            )
        );

        return _hashTypedDataV4(structHash);
    }

    function recoverProofSigner(ProofRequest calldata request, bytes calldata signature)
        public
        view
        returns (address)
    {
        bytes32 digest = getProofTypedDataHash(request);
        return digest.recover(signature);
    }

    /**
     * 기관이 전자서명한 Proof를 온체인에 앵커링한다.
     * msg.sender는 기관 지갑일 수도 있고, admin/relayer일 수도 있다.
     * 실제 Proof 발행 주체는 EIP-712 서명의 signer로 검증한다.
     */
    function anchorProof(
        uint256 caseId,
        uint256 stepId,
        bytes32 claimHash,
        bytes32 proofHash,
        VerificationStatus result,
        uint64 evidenceTimestamp,
        uint64 deadline,
        uint256 nonce,
        address agency,
        bytes calldata signature
    ) external onlyOpen(caseId) {
        require(isAuthorizedAgency(agency), "Agency is not authorized");
        require(stepId < cases[caseId].stepCount, "Step index out of bounds");
        require(claimHash != bytes32(0), "Claim hash is empty");
        require(proofHash != bytes32(0), "Proof hash is empty");
        require(deadline >= block.timestamp, "Signature expired");
        require(nonce == agencyNonces[agency], "Invalid or used nonce");

        AgencyInfo memory info = agencies[agency];
        require(info.active, "Agency is inactive");
        require(info.signer != address(0), "Agency signer not configured");

        ProofRequest memory request = ProofRequest({
            caseId: caseId,
            stepId: stepId,
            claimHash: claimHash,
            proofHash: proofHash,
            result: result,
            evidenceTimestamp: evidenceTimestamp,
            nonce: nonce,
            deadline: deadline,
            agency: agency
        });

        bytes32 digest = getProofTypedDataHash(request);
        address recoveredSigner = digest.recover(signature);
        require(recoveredSigner == info.signer, "Invalid electronic signature");

        // replay 방지
        agencyNonces[agency] = nonce + 1;

        Step storage step = caseSteps[caseId][stepId];
        step.claimHash = claimHash;
        step.proofHash = proofHash;
        step.status = result;
        step.isCompleted = (result == VerificationStatus.VERIFIED);

        uint256 proofId = nextProofId++;

        proofHistory[caseId][stepId].push(
            ProofRecord({
                proofId: proofId,
                agency: agency,
                signer: recoveredSigner,
                claimHash: claimHash,
                proofHash: proofHash,
                status: result,
                evidenceTimestamp: evidenceTimestamp,
                recordedAt: uint64(block.timestamp),
                signatureDigest: digest
            })
        );

        latestProofId[caseId][stepId] = proofId;

        emit ProofAnchored(
            caseId,
            stepId,
            proofId,
            agency,
            recoveredSigner,
            claimHash,
            proofHash,
            result,
            evidenceTimestamp,
            digest
        );
    }

    // FullProof v1.1 - 기관 독립 Proof 등록
    function anchorProofAttestation(
        ProofAttestation calldata request,
        bytes calldata signature
    )
        external
        onlyOpen(request.caseId)
    {
        // 1. 사건 단계 확인
        require(
            request.stepId < cases[request.caseId].stepCount,
            "Invalid step"
        );

        // 2. Proof 정보 확인
        require(
            request.proofIdHash != bytes32(0),
            "Invalid proof ID"
        );

        require(
            request.proofHash != bytes32(0),
            "Invalid proof hash"
        );

        require(
            request.occurredAt > 0 &&
            request.issuedAt >= request.occurredAt,
            "Invalid proof timestamps"
        );

        // 3. 기관 권한 확인
        require(
            isAuthorizedAgency(request.agency),
            "Agency is not authorized"
        );

        AgencyInfo memory info = agencies[request.agency];

        require(info.active, "Agency is inactive");
        require(
            info.signer != address(0),
            "Agency signer not configured"
        );

        // 4. 서명 만료 및 재사용 확인
        require(
            request.deadline >= block.timestamp,
            "Signature expired"
        );

        require(
            request.nonce == agencyNonces[request.agency],
            "Invalid or used nonce"
        );

        // 5. 기관 전자서명 검증
        address recoveredSigner =
            recoverProofAttestationSigner(request, signature);

        require(
            recoveredSigner == info.signer,
            "Invalid electronic signature"
        );

        
        // 6. 동일 Proof ID와 버전의 중복 등록 방지
        require(
            request.proofVersion > 0,
            "Invalid proof version"
        );

        bytes32 proofKey = keccak256(
            abi.encode(
                request.caseId,
                request.stepId,
                request.agency,
                request.proofIdHash,
                request.proofVersion
            )
        );


        require(
            !registeredAgencyProofs[proofKey],
            "Proof already registered"
        );

        registeredAgencyProofs[proofKey] = true;

        // 7. 서명 재사용 방지
        agencyNonces[request.agency] = request.nonce + 1;

        // 8. Proof 이력 저장
        bytes32 digest =
            getProofAttestationTypedDataHash(request);

        agencyProofHistory[request.caseId][request.stepId].push(
            AgencyProofRecord({
                proofIdHash: request.proofIdHash,
                proofVersion: request.proofVersion,
                proofHash: request.proofHash,
                agency: request.agency,
                signer: recoveredSigner,
                occurredAt: request.occurredAt,
                issuedAt: request.issuedAt,
                recordedAt: uint64(block.timestamp),
                signatureDigest: digest
            })
        );

        // 9. 등록 이벤트 발생
        emit AgencyProofAnchored(
            request.caseId,
            request.stepId,
            request.proofIdHash,
            request.proofVersion,
            request.proofHash,
            request.agency,
            recoveredSigner,
            request.occurredAt,
            request.issuedAt,
            uint64(block.timestamp),
            digest
        );
    }

    // FullProof v1.1 - 기관 Proof 이력 개수 조회
    function getAgencyProofHistoryLength(
        uint256 caseId,
        uint256 stepId
    ) external view returns (uint256) {
        return agencyProofHistory[caseId][stepId].length;
    }

    // FullProof v1.1 - 기관 Proof 개별 이력 조회
    function getAgencyProofRecord(
        uint256 caseId,
        uint256 stepId,
        uint256 index
    ) external view returns (AgencyProofRecord memory) {
        require(
            index < agencyProofHistory[caseId][stepId].length,
            "Invalid agency proof index"
        );

        return agencyProofHistory[caseId][stepId][index];
    }
    
    // 등록된 기관 Proof의 ID·버전·원문 해시 일치 여부 확인
    function isRegisteredAgencyProof(
        uint256 caseId,
        uint256 stepId,
        bytes32 proofIdHash,
        uint256 proofVersion,
        bytes32 proofHash
    ) public view caseExists(caseId) returns (bool) {
        require(
            stepId < cases[caseId].stepCount,
            "Invalid step"
        );

        AgencyProofRecord[] storage proofs =
            agencyProofHistory[caseId][stepId];

        for (uint256 i = 0; i < proofs.length; i++) {
            if (
                proofs[i].proofIdHash == proofIdHash &&
                proofs[i].proofVersion == proofVersion &&
                proofs[i].proofHash == proofHash
            ) {
                return true;
            }
        }

        return false;
    }
    
    // 해당 기관 Proof ID의 최신 버전과 해시 확인
    function isLatestAgencyProof(
        uint256 caseId,
        uint256 stepId,
        address agency,
        bytes32 proofIdHash,
        uint256 proofVersion,
        bytes32 proofHash
    ) public view caseExists(caseId) returns (bool) {
        require(
            stepId < cases[caseId].stepCount,
            "Invalid step"
        );

        AgencyProofRecord[] storage proofs =
            agencyProofHistory[caseId][stepId];

        bool found = false;
        uint256 highestVersion = 0;
        bytes32 highestVersionHash;

        for (uint256 i = 0; i < proofs.length; i++) {
            if (
                proofs[i].agency == agency &&
                proofs[i].proofIdHash == proofIdHash
            ) {
                if (!found || proofs[i].proofVersion > highestVersion) {
                    found = true;
                    highestVersion = proofs[i].proofVersion;
                    highestVersionHash = proofs[i].proofHash;
                }
            }
        }

        return (
            found &&
            highestVersion == proofVersion &&
            highestVersionHash == proofHash
        );
    }


    // -----------------------------
    // Case closing
    // -----------------------------

    
    // FullProof v1.1: 필수 단계의 종결 조건 확인
    function _checkCaseClosureConditions(
        uint256 caseId
    ) internal view {
        uint256 count = cases[caseId].stepCount;

        for (uint256 i = 0; i < count; i++) {
            // 필수 수사 단계만 종결 조건 검사
            if (!caseSteps[caseId][i].isRequired) {
                continue;
            }

            // 최신 Claim과 Verification의 참조 일치 여부
            require(
                isLatestClaimVerified(caseId, i),
                "Closure blocked: outdated Claim verification"
            );
            
            // 최신 Verification의 최종 판정 확인
            uint256 verificationCount =
                verificationHistory[caseId][i].length;

            VerificationRecord storage latestVerification =
                verificationHistory[caseId][i][verificationCount - 1];

            require(
                latestVerification.verdict == VerificationVerdict.SUPPORTED,
                "Closure blocked: verification not supported"
            );

            // Verification 이후 Proof 추가 여부
            require(
                isProofHistoryUnchanged(caseId, i),
                "Closure blocked: Proof history changed"
            );
            
            // Verification에서 사용한 Proof 참조 해시가 비어 있으면 종결 차단
            uint256 latestVerificationIndex =
                verificationHistory[caseId][i].length - 1;

            require(
                verificationHistory[caseId][i][latestVerificationIndex]
                    .proofRefsHash != bytes32(0),
                "Closure blocked: missing Proof references"
            );
            
            // 기관 Proof가 하나도 없으면 사건 종결 차단
            require(
                agencyProofHistory[caseId][i].length > 0,
                "Closure blocked: no agency Proof"
            );

            // 최신 Verification에 대한 관리자 승인 여부
            require(
                isLatestVerificationApproved(caseId, i),
                "Closure blocked: approval required"
            );
        }
    }

    
function closeCase(uint256 caseId, string memory reason)
    external
    onlyOpen(caseId)
    onlyAdmin
{
    require(bytes(reason).length > 0, "Close reason is empty");

    uint256 count = cases[caseId].stepCount;
    uint256 requiredCount = 0;

    for (uint256 i = 0; i < count; i++) {
        if (!caseSteps[caseId][i].isRequired) {
            continue;
        }

        requiredCount++;

        // 1. AI Verification 기록이 존재해야 함
        uint256 verificationCount =
            verificationHistory[caseId][i].length;

        require(
            verificationCount > 0,
            "Cannot close: no verification"
        );

        VerificationRecord storage latestVerification =
            verificationHistory[caseId][i][verificationCount - 1];

        // 2. 최신 AI 판정이 SUPPORTED여야 함
        require(
            latestVerification.verdict == VerificationVerdict.SUPPORTED,
            "Cannot close: verification not supported"
        );

        // 3. 최신 Claim과 Proof 상태를 유지해야 함
        require(
            isLatestClaimVerified(caseId, i),
            "Cannot close: outdated Claim"
        );

        require(
            isProofHistoryUnchanged(caseId, i),
            "Cannot close: Proof history changed"
        );

        require(
            agencyProofHistory[caseId][i].length > 0,
            "Cannot close: no agency Proof"
        );

        // 4. 관리자 검토 이력이 존재해야 함
        uint256 reviewCount =
            verificationReviewHistory[caseId][i].length;

        require(
            reviewCount > 0,
            "Cannot close: no admin review"
        );

        VerificationReviewRecord storage latestReview =
            verificationReviewHistory[caseId][i][reviewCount - 1];

        // 5. 최신 검토가 APPROVE여야 함
        require(
            latestReview.action == VerificationReviewAction.APPROVE,
            "Cannot close: not approved"
        );

        // 6. 승인이 최신 Verification에 대한 것이어야 함
        require(
            latestReview.verificationIdHash ==
                latestVerification.verificationIdHash &&
            latestReview.verificationHash ==
                latestVerification.verificationHash,
            "Cannot close: outdated approval"
        );
    }

    require(
        requiredCount > 0,
        "Cannot close: no required steps"
    );

    cases[caseId].status = CaseStatus.CLOSED;
    cases[caseId].closeReason = reason;
    cases[caseId].closedAt = uint64(block.timestamp);
    cases[caseId].closer = msg.sender;

    emit CaseClosed(caseId, reason, msg.sender, block.timestamp);
}


    // -----------------------------
    // View functions
    // -----------------------------

    // 기존 backend 6-return 인터페이스와 최대한 호환
    function getStepInfo(uint256 caseId, uint256 stepIndex)
        external
        view
        caseExists(caseId)
        returns (
            string memory stepName,
            bytes32 claimHash,
            bytes32 proofHash,
            VerificationStatus status,
            bool isCompleted,
            bool isRequired
        )
    {
        require(stepIndex < cases[caseId].stepCount, "Step index out of bounds");
        Step memory step = caseSteps[caseId][stepIndex];
        return (
            step.stepName,
            step.claimHash,
            step.proofHash,
            step.status,
            step.isCompleted,
            step.isRequired
        );
    }

    function getCaseAllSteps(uint256 caseId)
        external
        view
        caseExists(caseId)
        returns (Step[] memory)
    {
        uint256 count = cases[caseId].stepCount;
        Step[] memory steps = new Step[](count);

        for (uint256 i = 0; i < count; i++) {
            steps[i] = caseSteps[caseId][i];
        }

        return steps;
    }

    function getProofHistoryLength(uint256 caseId, uint256 stepId)
        external
        view
        caseExists(caseId)
        returns (uint256)
    {
        require(stepId < cases[caseId].stepCount, "Step index out of bounds");
        return proofHistory[caseId][stepId].length;
    }

    function getProofRecord(
        uint256 caseId,
        uint256 stepId,
        uint256 historyIndex
    ) external view caseExists(caseId) returns (ProofRecord memory) {
        require(stepId < cases[caseId].stepCount, "Step index out of bounds");
        require(historyIndex < proofHistory[caseId][stepId].length, "History index out of bounds");
        return proofHistory[caseId][stepId][historyIndex];
    }

    function getLatestProof(uint256 caseId, uint256 stepId)
        external
        view
        caseExists(caseId)
        returns (ProofRecord memory)
    {
        require(stepId < cases[caseId].stepCount, "Step index out of bounds");
        uint256 len = proofHistory[caseId][stepId].length;
        require(len > 0, "No proof history");
        return proofHistory[caseId][stepId][len - 1];
    }
}
