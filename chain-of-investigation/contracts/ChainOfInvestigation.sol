// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ChainOfInvestigation {
    address public owner;

    // 4상태 매핑: 0:PENDING, 1:SUPPORTED, 2:CONTRADICTED, 3:EXPIRING_SOON
    enum Status { PENDING, SUPPORTED, CONTRADICTED, EXPIRING_SOON }

    struct Step {
        uint256 stepId;
        string description;
        string proofHash;
        Status status;
        bool isCompleted;
    }

    struct Case {
        bytes32 caseId;
        bool exists;
        bool isClosed;
        string closeReason;
        uint256 stepCount;
        mapping(uint256 => Step) steps;
    }

    mapping(bytes32 => Case) public cases;
    mapping(address => bool) public isAuthorizedAgency;

    event CaseCreated(bytes32 indexed caseId);
    event StepAdded(bytes32 indexed caseId, uint256 indexed stepId);
    event ProofAnchored(bytes32 indexed caseId, uint256 indexed stepId, string proofHash, Status status);
    event CaseClosed(bytes32 indexed caseId, string reason);

    modifier onlyOwnerOrAgency() {
        require(msg.sender == owner || isAuthorizedAgency[msg.sender], "Unauthorized");
        _;
    }

    // [문제 2 해결] 종결된 사건은 변경 불가능하도록 차단하는 Modifier
    modifier onlyActiveCase(bytes32 _caseId) {
        require(cases[_caseId].exists, "Case does not exist");
        require(!cases[_caseId].isClosed, "Cannot modify: Case is already closed");
        _;
    }

    constructor() {
        owner = msg.sender;
        isAuthorizedAgency[msg.sender] = true;
    }

    function registerAgency(address _agency) external {
        require(msg.sender == owner, "Only owner");
        isAuthorizedAgency[_agency] = true;
    }

    function createCase(bytes32 _caseId) external onlyOwnerOrAgency {
        require(!cases[_caseId].exists, "Case already exists");
        Case storage c = cases[_caseId];
        c.caseId = _caseId;
        c.exists = true;
        emit CaseCreated(_caseId);
    }

    function addStep(bytes32 _caseId, string memory _description) external onlyOwnerOrAgency onlyActiveCase(_caseId) {
        Case storage c = cases[_caseId];
        uint256 newStepId = c.stepCount;
        c.steps[newStepId] = Step(newStepId, _description, "", Status.PENDING, false);
        c.stepCount++;
        emit StepAdded(_caseId, newStepId);
    }

    function anchorProof(
        bytes32 _caseId,
        uint256 _stepId,
        string memory _proofHash,
        Status _status
    ) external onlyOwnerOrAgency onlyActiveCase(_caseId) {
        require(_stepId < cases[_caseId].stepCount, "Step index out of range");

        Step storage s = cases[_caseId].steps[_stepId];
        s.proofHash = _proofHash;
        s.status = _status;
        s.isCompleted = (_status == Status.SUPPORTED);

        emit ProofAnchored(_caseId, _stepId, _proofHash, _status);
    }

    // [문제 2 해결] 미검증/불일치 STEP이 존재하면 종결 불가 + 관리자/등록기관 전용 종결
    function closeCase(bytes32 _caseId, string memory _reason) external onlyOwnerOrAgency onlyActiveCase(_caseId) {
        Case storage c = cases[_caseId];
        
        for (uint256 i = 0; i < c.stepCount; i++) {
            require(c.steps[i].status != Status.CONTRADICTED, "Cannot close case: Contradicted step exists");
            require(c.steps[i].status == Status.SUPPORTED, "Cannot close case: Unverified step exists");
        }

        c.isClosed = true;
        c.closeReason = _reason;
        emit CaseClosed(_caseId, _reason);
    }

    // [문제 4 해결] 온체인 정보 조회를 위한 View 함수
    function getStepInfo(bytes32 _caseId, uint256 _stepId) external view returns (string memory description, string memory proofHash, Status status, bool isCompleted) {
        Step storage s = cases[_caseId].steps[_stepId];
        return (s.description, s.proofHash, s.status, s.isCompleted);
    }
}