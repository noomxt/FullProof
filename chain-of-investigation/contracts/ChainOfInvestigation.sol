// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ChainOfInvestigation {
    
    address public admin; 
    mapping(address => bool) public isPolice;  
    mapping(address => bool) public isTelecom; 
    mapping(address => bool) public isCCTV;    
    
    mapping(uint256 => address) public caseFamily; 

    enum VerificationStatus { PENDING, VERIFIED, MISMATCH, EXPIRING_SOON }
    enum CaseStatus { OPEN, CLOSED }

    // [이벤트 복구] 온체인 동기화 및 감사 트레일용
    event CaseCreated(uint256 indexed caseId, address indexed creator);
    event StepAdded(uint256 indexed caseId, uint256 indexed stepId, string stepName, bool isRequired);
    event ProofAnchored(
        uint256 indexed caseId, 
        uint256 indexed stepId, 
        bytes32 claimHash, 
        bytes32 proofHash, 
        VerificationStatus status
    );
    event CaseClosed(uint256 indexed caseId, string reason);

    struct Step {
        string stepName;      
        bool isRequired;           
        VerificationStatus status;
        bytes32 claimHash;
        bytes32 proofHash;
        bool isCompleted;
    }

    struct Case {
        uint256 caseId;
        CaseStatus status;
        uint256 stepCount;
        bool exists;         // [문제 5 해결] 사건 존재 여부 플래그
        string closeReason;  // [문제 6 해결] 종결 사유 기록
    }

    mapping(uint256 => Case) public cases;
    mapping(uint256 => mapping(uint256 => Step)) public caseSteps;

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only Admin can do this");
        _;
    }

    modifier caseExists(uint256 _caseId) {
        require(cases[_caseId].exists, "Case does not exist");
        _;
    }

    modifier onlyOpen(uint256 _caseId) {
        require(cases[_caseId].exists, "Case does not exist");
        require(cases[_caseId].status == CaseStatus.OPEN, "Case is already CLOSED");
        _;
    }

    constructor() {
        admin = msg.sender;
        isPolice[msg.sender] = true; // 최초 배포자를 경찰 권한으로 자동 등록
    }

    // [문제 2 해결] 백엔드가 호출하는 통합 기관 권한 검증 함수
    function isAuthorizedAgency(address _agency) public view returns (bool) {
        return isPolice[_agency] || isTelecom[_agency] || isCCTV[_agency] || _agency == admin;
    }

    function registerAgency(address _agency, string memory _type) public onlyAdmin {
        bytes32 typeHash = keccak256(bytes(_type));
        if (typeHash == keccak256(bytes("POLICE"))) isPolice[_agency] = true;
        else if (typeHash == keccak256(bytes("TELECOM"))) isTelecom[_agency] = true;
        else if (typeHash == keccak256(bytes("CCTV"))) isCCTV[_agency] = true;
    }

    function registerFamilyWallet(uint256 _caseId, address _familyWallet) public onlyOpen(_caseId) {
        require(isPolice[msg.sender] || msg.sender == admin, "Only Police/Admin can register family");
        caseFamily[_caseId] = _familyWallet;
    }

    // [문제 5 해결] 중복 생성 및 미존재 사건 생성 제어
    function createCase(uint256 _caseId) public {
        require(isPolice[msg.sender] || msg.sender == admin, "Only Police/Admin can create case");
        require(!cases[_caseId].exists, "Case already exists");
        
        cases[_caseId] = Case({ 
            caseId: _caseId, 
            status: CaseStatus.OPEN, 
            stepCount: 0,
            exists: true,
            closeReason: ""
        });

        emit CaseCreated(_caseId, msg.sender);
    }

    function addStep(uint256 _caseId, string memory _stepName, bool _isRequired) public onlyOpen(_caseId) {
        require(isPolice[msg.sender] || msg.sender == admin, "Only Police/Admin can add step");
        uint256 stepIndex = cases[_caseId].stepCount;
        
        caseSteps[_caseId][stepIndex] = Step({
            stepName: _stepName,
            isRequired: _isRequired,
            status: VerificationStatus.PENDING,
            claimHash: bytes32(0),
            proofHash: bytes32(0),
            isCompleted: false
        });
        cases[_caseId].stepCount++;

        emit StepAdded(_caseId, stepIndex, _stepName, _isRequired);
    }

    // [문제 2 해결] 백엔드 규격과 합치된 5인자 anchorProof
    function anchorProof(
        uint256 _caseId, 
        uint256 _stepIndex,
        bytes32 _claimHash, 
        bytes32 _proofHash, 
        VerificationStatus _result
    ) public onlyOpen(_caseId) {
        require(isAuthorizedAgency(msg.sender), "Not an authorized agency");
        require(_stepIndex < cases[_caseId].stepCount, "Step index out of bounds");
        
        Step storage step = caseSteps[_caseId][_stepIndex];
        step.claimHash = _claimHash;
        step.proofHash = _proofHash;
        step.status = _result;
        step.isCompleted = (_result == VerificationStatus.VERIFIED);
        
        emit ProofAnchored(_caseId, _stepIndex, _claimHash, _proofHash, _result);
    }

    function closeCase(uint256 _caseId, string memory _reason) public onlyOpen(_caseId) onlyAdmin {
        uint256 count = cases[_caseId].stepCount;
        for (uint256 i = 0; i < count; i++) {
            if (caseSteps[_caseId][i].isRequired) {
                require(
                    caseSteps[_caseId][i].status == VerificationStatus.VERIFIED,
                    "Cannot close: All required steps must be VERIFIED"
                );
            }
        }
        cases[_caseId].status = CaseStatus.CLOSED;
        cases[_caseId].closeReason = _reason;

        emit CaseClosed(_caseId, _reason);
    }

    // [문제 2, 4 해결] 온체인 복구용 단일 Step 조회 함수
    function getStepInfo(uint256 _caseId, uint256 _stepIndex) public view caseExists(_caseId) returns (
        string memory stepName,
        bytes32 claimHash,
        bytes32 proofHash,
        VerificationStatus status,
        bool isCompleted,
        bool isRequired
    ) {
        require(_stepIndex < cases[_caseId].stepCount, "Step index out of bounds");
        Step memory st = caseSteps[_caseId][_stepIndex];
        return (st.stepName, st.claimHash, st.proofHash, st.status, st.isCompleted, st.isRequired);
    }

    function getCaseAllSteps(uint256 _caseId) public view caseExists(_caseId) returns (Step[] memory) {
        uint256 count = cases[_caseId].stepCount;
        Step[] memory steps = new Step[](count);
        for (uint256 i = 0; i < count; i++) {
            steps[i] = caseSteps[_caseId][i];
        }
        return steps;
    }
}