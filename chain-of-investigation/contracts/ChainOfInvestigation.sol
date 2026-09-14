// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ChainOfInvestigation {
    
    // 1. 역할(지갑 주소) 관리
    address public admin; 
    mapping(address => bool) public isPolice;  
    mapping(address => bool) public isTelecom; 
    mapping(address => bool) public isCCTV;    
    
    mapping(uint256 => address) public caseFamily; 

    // 🌟 수정됨: API 응답(4상태)과 온체인 상태 완벽 동기화
    enum VerificationStatus { PENDING, VERIFIED, MISMATCH, EXPIRING_SOON }
    enum CaseStatus { OPEN, CLOSED }

    event ProofAnchored(
        uint256 indexed caseId, 
        uint256 indexed stepId, 
        bytes32 claimHash, 
        bytes32 proofHash, 
        VerificationStatus status
    );

    struct Step {
        string stepName;      
        bool isRequired;           
        VerificationStatus status; 
    }

    struct Case {
        uint256 caseId;
        CaseStatus status;
        uint256 stepCount;
    }

    mapping(uint256 => Case) public cases;
    mapping(uint256 => mapping(uint256 => Step)) public caseSteps;

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only Admin can do this");
        _;
    }

    // 🌟 수정됨: 사건 종결 후 데이터 변경 원천 차단 (지적 2번 해결)
    modifier onlyOpen(uint256 _caseId) {
        require(cases[_caseId].status == CaseStatus.OPEN, "Case is already CLOSED");
        _;
    }

    constructor() {
        admin = msg.sender; 
    }

    function registerAgency(address _agency, string memory _type) public onlyAdmin {
        if (keccak256(bytes(_type)) == keccak256(bytes("POLICE"))) isPolice[_agency] = true;
        else if (keccak256(bytes(_type)) == keccak256(bytes("TELECOM"))) isTelecom[_agency] = true;
        else if (keccak256(bytes(_type)) == keccak256(bytes("CCTV"))) isCCTV[_agency] = true;
    }

    function registerFamilyWallet(uint256 _caseId, address _familyWallet) public onlyOpen(_caseId) {
        require(isPolice[msg.sender], "Only Police can register family");
        caseFamily[_caseId] = _familyWallet;
    }

    function createCase(uint256 _caseId) public {
        require(isPolice[msg.sender], "Only Police can create case");
        require(cases[_caseId].stepCount == 0, "Case already exists");
        cases[_caseId] = Case({ caseId: _caseId, status: CaseStatus.OPEN, stepCount: 0 });
    }

    function addStep(uint256 _caseId, string memory _stepName, bool _isRequired) public onlyOpen(_caseId) {
        require(isPolice[msg.sender], "Only Police can add step");
        uint256 stepIndex = cases[_caseId].stepCount;
        
        caseSteps[_caseId][stepIndex] = Step({
            stepName: _stepName,
            isRequired: _isRequired,
            status: VerificationStatus.PENDING
        });
        cases[_caseId].stepCount++;
    }

    // 🌟 수정됨: Admin 대리 앵커링 삭제, 실제 기관 권한 검증 (지적 1번 해결)
    function anchorProof(
        uint256 _caseId, 
        uint256 _stepIndex,
        bytes32 _claimHash, 
        bytes32 _proofHash, 
        VerificationStatus _result
    ) public onlyOpen(_caseId) {
        // 증명 주체(원천기관)가 맞는지 확인
        require(isPolice[msg.sender] || isTelecom[msg.sender] || isCCTV[msg.sender], "Not an authorized agency");
        
        caseSteps[_caseId][_stepIndex].status = _result;
        
        emit ProofAnchored(_caseId, _stepIndex, _claimHash, _proofHash, _result);
    }

    function closeCase(uint256 _caseId) public onlyOpen(_caseId) onlyAdmin {
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
    }

    // 🌟 수정됨: 서버 메모리 초기화 시 온체인 데이터로 사건 복구 지원 (지적 4번 해결)
    function getCaseAllSteps(uint256 _caseId) public view returns (Step[] memory) {
        uint256 count = cases[_caseId].stepCount;
        Step[] memory steps = new Step[](count);
        for (uint256 i = 0; i < count; i++) {
            steps[i] = caseSteps[_caseId][i];
        }
        return steps;
    }
}