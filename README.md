<div align="center">

# 🔎 FullProof

### 수사했다는 기록이 아니라, 수사했다는 증거.

AI와 블록체인을 활용해 수사 기록의 주장(Claim)과  
기관의 수행 증빙(Proof)을 교차 검증하는 수사 절차 검증 시스템

![Status](https://img.shields.io/badge/status-planning-F59E0B?style=for-the-badge)
![AI](https://img.shields.io/badge/AI-semantic%20verification-8B5CF6?style=for-the-badge)
![Blockchain](https://img.shields.io/badge/blockchain-EVM-3C3C3D?style=for-the-badge)

</div>

---

## 💡 프로젝트 소개

기존의 Chain of Custody가 확보된 증거의 위·변조 여부를 검증한다면, FullProof의 Chain of Investigation은 그 증거를 확보하기 위한 수사행위가 실제로 수행되었는지를 검증합니다.

> “증거가 바뀌지 않았는가?”를 넘어  
> “필요한 수사행위를 실제로 수행했는가?”를 확인합니다.

현재 **BLOCK AI 26 해커톤** 출품을 목표로 MVP를 설계하고 있습니다.

## 🚨 해결하려는 문제

| 문제 | 설명 |
| --- | --- |
| 🔴 **Claim-Proof Mismatch** | 수행했다고 기록했지만 증빙이 없거나 기록과 실제 증빙이 일치하지 않는 경우 |
| ⏳ **Time-Critical Evidence Miss** | 조치가 지연되어 CCTV 등 시한성 증거가 소멸할 위험이 있는 경우 |

## ✨ 핵심 솔루션

1. 🗂️ 사건 유형에 맞는 필수 수사 절차를 구성합니다.
2. ✍️ 담당자가 수행한 수사행위를 **Claim**으로 기록합니다.
3. 🏢 관계 기관이 수행 증빙인 **Proof**를 발행하고 전자서명합니다.
4. 🤖 AI와 규칙 기반 엔진이 Claim과 Proof를 교차 검증합니다.
5. ⛓️ Proof 해시와 검증 결과를 블록체인에 기록합니다.
6. 📊 관리자가 이상 징후와 시한성 증거 경고를 확인합니다.

> [!IMPORTANT]
> AI는 이상 징후를 탐지하고 경고하는 역할만 수행합니다. 사건 종결, 책임 소재 또는 범죄 혐의에 관한 최종 판단은 항상 사람이 담당합니다.

## 🧪 MVP 데모 시나리오

| 시나리오 | 상황 | 결과 |
| --- | --- | --- |
| ✅ 정상 수사 | Claim과 기관 Proof의 대상·행위·시간이 일치 | `VERIFIED` |
| ❌ 기록 불일치 | Claim에 대응하는 Proof가 없거나 대상이 다름 | `CLAIM_PROOF_MISMATCH` |
| 🚨 시한성 증거 | CCTV가 미확보 상태이며 보존기한이 임박 | `HIGH_PRIORITY` |

## 🏗️ 시스템 구조

```text
사건 관리 시스템
       ↓
수사 절차 Template Engine
       ↓
AI Investigation Proof Engine
 ├─ Semantic Matching
 └─ Rule Validation
       ↓
Verification Result
       ↓
Smart Contract / Investigation Ledger
       ↓
관리자 Dashboard
```

## 🛠️ 기술 스택

| 영역 | 기술 |
| --- | --- |
| 🖥️ Frontend | React |
| ⚙️ Backend | FastAPI, Python |
| 🤖 AI | LLM 또는 Embedding 기반 Semantic Matching |
| ✅ Rule Engine | Python |
| ⛓️ Blockchain | Solidity, EVM Testnet, ethers.js |
| 🗄️ Database | PostgreSQL 또는 Firebase |
| 🔐 Authentication | 기관별 Wallet Signature |

## 🎯 MVP 구현 범위

- [ ] 실종사건 수사 절차 템플릿
- [ ] AI 기반 수사 STEP 추천
- [ ] 담당자 Claim 등록
- [ ] Mock 기관 Proof 발행
- [ ] 기관 Wallet 전자서명
- [ ] Claim-Proof 의미 비교 및 규칙 검증
- [ ] 검증 결과 테스트넷 기록
- [ ] 관리자용 불일치 알림
- [ ] CCTV 보존기한 경고

## 🔐 개인정보 보호

통화기록 원문, 위치정보, CCTV 영상과 사건기록은 블록체인에 직접 저장하지 않습니다.

민감정보는 암호화된 오프체인 저장소에 보관하고, 블록체인에는 Proof Hash, 기관 ID, 전자서명, 발행 시각과 검증 결과 등 최소한의 정보만 기록합니다.

## 🚧 개발 상태

**Planning & Early Development**

해커톤 MVP에서는 실제 기관 시스템이나 개인정보를 사용하지 않습니다. Mock 데이터와 기관별 테스트 Wallet을 이용해 다기관 환경을 시뮬레이션합니다.

## ⚖️ Disclaimer

FullProof는 해커톤을 위한 프로토타입이며 어떠한 수사기관과도 관련이 없습니다. 법적·징계적·수사상 판단을 자동으로 내리는 용도로 사용할 수 없습니다.

---

<div align="center">

**FullProof · BLOCK AI 26**

</div>
