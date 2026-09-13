// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ChainOfInvestigation {
    address public owner;

    // 기획서 및 백엔드 4상태 매핑: 0:PENDING, 1:SUPPORTED(VERIFIED), 2:CONTRADICTED(MISMATCH), 3:EXPIRING_SOON
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
        require(msg.sender == owner || isAuthorizedAgency[msg.sender], "Unauthorized: Only Owner or Registered Agency");
        _;
    }

    constructor() {
        owner = msg.sender;
        isAuthorizedAgency[msg.sender] = true;
    }

    function registerAgency(address _agency) external {
        require(msg.sender == owner, "Only owner can register agency");
        isAuthorizedAgency[_agency] = true;
    }

    function createCase(bytes32 _caseId) external onlyOwnerOrAgency {
        require(!cases[_caseId].exists, "Case already exists");
        Case storage c = cases[_caseId];
        c.caseId = _caseId;
        c.exists = true;
        emit CaseCreated(_caseId);
    }

    function addStep(bytes32 _caseId, string memory _description) external onlyOwnerOrAgency {
        require(cases[_caseId].exists, "Case does not exist");
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
    ) external onlyOwnerOrAgency {
        require(cases[_caseId].exists, "Case does not exist");
        require(_stepId < cases[_caseId].stepCount, "Step index out of range");

        Step storage s = cases[_caseId].steps[_stepId];
        s.proofHash = _proofHash;
        s.status = _status;
        s.isCompleted = (_status == Status.SUPPORTED);

        emit ProofAnchored(_caseId, _stepId, _proofHash, _status);
    }

    function closeCase(bytes32 _caseId, string memory _reason) external onlyOwnerOrAgency {
        require(cases[_caseId].exists, "Case does not exist");
        Case storage c = cases[_caseId];
        c.isClosed = true;
        c.closeReason = _reason;
        emit CaseClosed(_caseId, _reason);
    }
}