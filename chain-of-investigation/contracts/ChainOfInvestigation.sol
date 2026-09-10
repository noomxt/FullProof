// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ChainOfInvestigation {
    
    // 1. 역할(지갑 주소) 관리
    address public admin; 
    mapping(address => bool) public isPolice;  
    mapping(address => bool) public isTelecom; 
    mapping(address => bool) public isCCTV;    
    
    // 🌟 [추가됨] 특정 사건(Case ID)에 매칭된 유가족 지갑 주소
    mapping(uint256 => address) public caseFamily; 

    // 2. 검증 상태 및 사건 상태 정의
    enum VerificationStatus { PENDING, VERIFIED, MISMATCH }
    enum CaseStatus { OPEN, CLOSED }

    // 3. 수사 STEP 구조체
    struct Step {
        string stepName;      
        bool isRequired;           
        VerificationStatus status; 
    }

    // 4. 사건 구조체
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

    constructor() {
        admin = msg.sender; 
    }

    // [기능 1] 기관 지갑 등록
    function registerAgency(address _agency, string memory _type) public onlyAdmin {
        if (keccak256(bytes(_type)) == keccak256(bytes("POLICE"))) isPolice[_agency] = true;
        else if (keccak256(bytes(_type)) == keccak256(bytes("TELECOM"))) isTelecom[_agency] = true;
        else if (keccak256(bytes(_type)) == keccak256(bytes("CCTV"))) isCCTV[_agency] = true;
    }

    // 🌟 [추가됨] 사건 발생 시 유가족 지갑 주소 등록 (경찰이 진행)
    function registerFamilyWallet(uint256 _caseId, address _familyWallet) public {
        require(isPolice[msg.sender] || msg.sender == admin, "Not authorized");
        caseFamily[_caseId] = _familyWallet;
    }

    // [기능 2] 사건 생성 및 STEP 추가
    function createCase(uint256 _caseId) public {
        require(isPolice[msg.sender] || msg.sender == admin, "Not authorized");
        cases[_caseId] = Case({ caseId: _caseId, status: CaseStatus.OPEN, stepCount: 0 });
    }

    function addStep(uint256 _caseId, string memory _stepName, bool _isRequired) public {
        require(isPolice[msg.sender] || msg.sender == admin, "Not authorized");
        uint256 stepIndex = cases[_caseId].stepCount;
        
        caseSteps[_caseId][stepIndex] = Step({
            stepName: _stepName,
            isRequired: _isRequired,
            status: VerificationStatus.PENDING
        });
        cases[_caseId].stepCount++;
    }

    // [기능 3] Proof 검증 완료 앵커링
    function anchorProof(
        uint256 _caseId, uint256 _stepIndex,
        bytes32 /* _claimHash */, bytes32 /* _proofHash */, VerificationStatus _result
    ) public {
        caseSteps[_caseId][_stepIndex].status = _result;
    }

    // [기능 4] 사건 최종 종결 처리 (관리자 승인)
    function closeCase(uint256 _caseId) public onlyAdmin {
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

    // 🌟 [추가됨] 유가족 전용 사건 투명성 조회 (대시보드용 읽기 전용 함수)
    function getStepInfoForFamily(uint256 _caseId, uint256 _stepIndex) public view returns (string memory, bool, VerificationStatus) {
        // 호출자가 해당 사건의 유가족이거나, 경찰/관리자일 때만 열람 허용 (프라이버시 보호)
        require(msg.sender == caseFamily[_caseId] || isPolice[msg.sender] || msg.sender == admin, "No read access for this case");
        
        Step memory step = caseSteps[_caseId][_stepIndex];
        return (step.stepName, step.isRequired, step.status);
    }
}