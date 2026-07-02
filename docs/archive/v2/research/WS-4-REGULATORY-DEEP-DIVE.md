# WS-4: Standards & Regulation - Deep Analysis

> **Part of the Agentic Guardrails, Compliance, Standardisation & Security research programme**
> Status: **COMPLETE** | Last updated: 2026-05-25

--

## 1. Research Scope & Questions

### 1.1 EU AI Act

**Key questions:**
- Article 12 (record-keeping / automatic logging): exact requirements for agent audit trails
- Article 14 (human oversight): what does this mean for autonomous agents? Override/interrupt requirements
- Article 26 (deployer duties): enterprise obligations when deploying AI agents
- Article 6 / Annex III (high-risk classification): when do agents trigger high-risk?
- Delegated acts expected 2026 - timeline and content
- Penalties timeline and enforcement structure
- Implementation deadlines and transition periods

### 1.2 ISO/IEC 42001 (AIMS)

**Key questions:**
- AIMS management system controls mapped to agent lifecycle
- Specific documentation requirements for agent certification
- Integration requirements with ISO 27001 (ISMS)
- Gap analysis for AMI-Agents against ISO 42001 clauses
- Certification process and timeline
- Interaction with EU AI Act (harmonised standard status)

### 1.3 NIST AI RMF + NIST AI 600-1

**Key questions:**
- Govern, Map, Measure, Manage functions applied to agentic AI
- Generative AI profile specifics relevant to agents
- NIST Secure AI Development framework
- NIST publications expected in 2026
- US AI policy implications for agent deployments

### 1.4 OWASP / ETSI / CEN-CENELEC

**Key questions:**
- OWASP Top 10 for LLM Applications - agent-specific entries
- OWASP Agentic AI Security landscape (new developments)
- ETSI AI security standards (ETSI SAI ISG)
- CEN-CENELEC standards under EU AI Act harmonisation (expected 2026)
- Harmonised standards process and status

### 1.5 DORA / NIS2 / GDPR

**Key questions:**
- DORA (Digital Operational Resilience Act): ICT risk management for agent systems
- NIS2: incident reporting obligations for agent infrastructure
- GDPR Article 22 (automated decision-making): applicability to agentic workflows
- Cross-regulation interaction: DORA + EU AI Act + GDPR for agent deployments
- Relevant guidance from EDPB and ENISA

### 1.6 MLCommons AI Safety

**Key questions:**
- ML Safety benchmark status and scope
- Agent-specific safety testing protocols
- Working groups: who is participating
- Frontier Model Forum commitments and deliverables

--

## 2. Regulatory Requirements Matrix

| Regulation | Agent-Relevant Articles / Clauses | Key Requirements | Enforcement Date | Penalties |
|--|--|--|--|--|
| **EU AI Act** | Art. 12, 14, 26, 6, 99; Annex III | Automated logging, human oversight, deployer duties, risk classification, conformity assessment | 2 Aug 2026 (most); 2 Feb 2025 (prohibitions); 2 Aug 2027 (Art. 6(1)) | Up to 35M EUR or 7% turnover (Art. 5 violations); 15M EUR or 3% (Art. 12-26 violations); 7.5M EUR or 1% (incorrect info) |
| **ISO/IEC 42001:2023** | All clauses (4-10) | AIMS: AI policy, risk assessment, impact assessment, lifecycle management, documentation | Published Dec 2023; certification available now | N/A (voluntary standard, but cited for EU AI Act conformity presumption) |
| **ISO/IEC 27001:2022** | Annex A controls | Information security management integration with AIMS | Published Oct 2022 | N/A (voluntary, but mandated by DORA indirectly) |
| **NIST AI RMF 1.0** | Govern, Map, Measure, Manage (all 4 functions) | Risk management framework for AI systems; core functions mapped to agent lifecycle | Published Jan 2023; updated 2025 | N/A (voluntary US framework) |
| **NIST AI 600-1** | Generative AI profile | Specific controls for GenAI including agent-specific risks (tool use, delegation) | Published Jul 2024 | N/A (voluntary) |
| **DORA** | Art. 5-16 (ICT risk management), Art. 17-23 (incident reporting) | ICT risk management for financial entities using AI agents; mandatory testing; third-party risk | 17 Jan 2025 (full application) | Up to 2% of daily avg turnover (penalties); individual fines up to 5M EUR |
| **NIS2** | Art. 20-23 (incident reporting), Art. 24-28 (risk management) | Incident reporting for digital infrastructure operators; supply chain security for AI systems | 17 Oct 2024 (transposition deadline) | Up to 10M EUR or 2% of turnover |
| **GDPR Art. 22** | Art. 22(1)-(4) | Right not to be subject to solely automated decisions; requires human intervention right; profiling restrictions | 25 May 2018 (in force) | Up to 20M EUR or 4% of turnover |
| **EDPB Guidelines** | Guidelines 8/2022, 3/2024 | DPIA requirements for AI; automated decision-making guidance | Ongoing | Referenced in GDPR enforcement |
| **CEN-CENELEC JTC 21** | AI standards pipeline | Harmonised EU standards for AI Act compliance (risk management, logging, transparency) | First standards due 2026-2027 | N/A (standards enable conformity presumption) |
| **ETSI SAI** | SAI-001, SAI-002, SAI-005 | AI security process framework; AI threat mitigation; AI security testing | Published 2023-2025 | N/A |
| **OWASP LLM Top 10** | LLM01-LLM10 (v1.1), v2025 updated | Prompt injection, insecure output, excessive agency, supply chain, plugin security | v1.1 2023; v2025 published | N/A (industry best practice) |
| **MLCommons AI Safety** | AI Safety v1.0 benchmarks | Safety benchmark suite for frontier models; agent-specific evaluations under development | First results Mar 2025 | N/A (voluntary testing framework) |

--

## 3. Detailed Findings

### 3.1 EU AI Act (Regulation (EU) 2024/1689)

#### 3.1.1 Article 12 - Record-Keeping (Automatic Logging)

**Effective from:** 2 August 2026

**Exact requirements:**

1. **Paragraph 1:** High-risk AI systems shall technically allow for the automatic recording of events (logs) over the lifetime of the system.

2. **Paragraph 2:** Logging capabilities must enable recording of events relevant for:
   - (a) identifying situations that may result in the system presenting a risk (Art. 79(1)) or a substantial modification
   - (b) facilitating post-market monitoring (Art. 72)
   - (c) monitoring the operation of high-risk AI systems (Art. 26(5))

3. **Paragraph 3 (minimum for Annex III point 1(a) systems - biometric identification):**
   - (a) recording of the period of each use (start date/time and end date/time)
   - (b) the reference database against which input data has been checked
   - (c) the input data for which the search led to a match
   - (d) identification of natural persons involved in verification of results (Art. 14(5))

**Relevant Recitals:** 66, 71

**Agent-specific implications:**
- For autonomous agents, this requires continuous logging of: all tool calls, decisions, context windows used, model outputs, human override events, state transitions
- Logs must be retained for **at least 6 months** (Art. 26(6)) - deployer obligation
- Logs must be "automatically generated" - cannot rely on manual reporting
- Technical architecture MUST include an immutable audit trail

#### 3.1.2 Article 14 - Human Oversight

**Effective from:** 2 August 2026

**Exact requirements:**

1. **Paragraph 1:** High-risk AI systems shall be designed and developed with appropriate human-machine interface tools so they can be effectively overseen by natural persons during use.

2. **Paragraph 2:** Human oversight aims to prevent or minimise risks to health, safety or fundamental rights.

3. **Paragraph 3:** Oversight measures shall be commensurate with:
   - Level of autonomy
   - Context of use
   - Risks
   
   Measures can be:
   - (a) built into the system by the provider (when technically feasible)
   - (b) identified for implementation by the deployer

4. **Paragraph 4:** Systems must enable natural persons to:
   - (a) properly understand capacities and limitations
   - (b) remain aware of automation bias
   - (c) correctly interpret output
   - (d) decide NOT to use the system, or **disregard, override or reverse** the output
   - (e) **intervene or interrupt** the system through a **'stop' button** or similar procedure that brings the system to a **halt in a safe state**

5. **Paragraph 5 (biometric identification systems - Annex III point 1(a)):** Requires separate verification by at least **two natural persons** with necessary competence, training and authority. Exception for law enforcement, migration, border control, asylum where disproportionate.

**Agent-specific implications:**
- **Stop button requirement:** Every autonomous agent MUST have a mechanism for safe halting. This is not optional - it is a legal requirement for high-risk systems. AMI-Agents must implement: graceful shutdown, safe state transitions, interrupt handling.
- **Override capability:** Human operators must be able to override, reverse, or disregard any agent decision.
- **Automation bias awareness:** The system design must help humans remain aware of automation bias.
- **Two-person rule:** For biometric-related agent systems, dual verification is mandatory.

#### 3.1.3 Article 26 - Obligations of Deployers

**Effective from:** 2 August 2026

**Key obligations:**

1. **Paragraph 1:** Take appropriate technical and organisational measures to ensure use in accordance with instructions.

2. **Paragraph 2:** Assign human oversight to persons with necessary competence, training, authority and support.

3. **Paragraph 4:** If deployer controls input data, ensure it is relevant and sufficiently representative.

4. **Paragraph 5:** Monitor operation of the system. If risk identified, inform provider/distributor AND market surveillance authority AND **suspend use**. If serious incident, immediately inform provider.

5. **Paragraph 6:** Keep automatically generated logs for at least **6 months** (unless longer under applicable law).

6. **Paragraph 7:** Before putting into service at workplace, inform workers' representatives and affected workers.

7. **Paragraph 8:** Public authorities must check registration in EU database before using.

8. **Paragraph 9:** Use information from Art. 13 to comply with DPIA obligations under GDPR Art. 35.

**Agent-specific implications for deployers:**
- Enterprises deploying AMI-Agents must:
  - Maintain logs for 6+ months
  - Suspend agent use if risk is identified
  - Provide human oversight with training
  - Inform workers before deployment
  - Ensure input data quality (for agents processing company data)

#### 3.1.4 Article 6 / Annex III - High-Risk Classification

**Classification rules:**

**Art. 6(1) - Product safety component rule (effective 2 Aug 2027):**
An AI system is high-risk if:
- (a) Intended as safety component of a product OR AI system is itself a product covered by EU harmonisation legislation listed in Annex I
- (b) The product requires third-party conformity assessment

**Art. 6(2) - Annex III rule (effective 2 Aug 2026):**
AI systems listed in Annex III are ALWAYS high-risk unless they satisfy the derogation in Art. 6(3).

**Annex III categories that could apply to AI agents:**

| Annex III Category | Relevant to Agents? | Scenario |
|--|--|--|
| 1. Biometrics (remote ID, categorisation, emotion) | Yes | Agent with vision capabilities |
| 2. Critical infrastructure safety components | Yes | Agent managing power/water/transport systems |
| 3. Education: access, evaluation, monitoring | Yes | Agent evaluating student work |
| 4. Employment: recruitment, task allocation, monitoring | **HIGH** | Agent managing worker tasks, evaluating performance |
| 5. Essential services: benefits, credit, insurance, emergency | **HIGH** | Agent making decisions on access to services |
| 6. Law enforcement | Yes | Agent used by law enforcement |
| 7. Migration, asylum, border control | Yes | Agent processing visa/immigration |
| 8. Administration of justice, democratic processes | Yes | Agent assisting judicial decisions |

**Art. 6(3) - Derogation (escape from high-risk classification):**
An Annex III system is NOT high-risk if it does not pose significant risk of harm, AND:
- (a) performs a narrow procedural task; OR
- (b) improves result of completed human activity; OR
- (c) detects decision-making patterns without replacing human assessment; OR
- (d) performs a preparatory task to an assessment

**However:** Profiling of natural persons always means high-risk, regardless of above.

**Art. 6(4):** Provider must document assessment if claiming non-high-risk. Register under Art. 49(2).

**Agent-specific implications:**
- An agent that assists with recruitment screening (Annex III 4(a)) is **automatically high-risk** unless it passes narrow procedural task derogation
- An agent that evaluates creditworthiness (Annex III 5(b)) is high-risk
- An agent that allocates emergency services (Annex III 5(d)) is high-risk
- Any agent that profiles individuals is ALWAYS high-risk regardless of derogation
- **Practical guidance for AMI-Agents:** Document the classification decision for every agent use case, especially if claiming non-high-risk under Art. 6(3)

#### 3.1.5 Delegated Acts Expected 2026

Per the implementation timeline:

| Date | Action |
|--|--|
| **2 Feb 2026** | Commission guidelines on Art. 6 classification rules (practical implementation + examples of high-risk/not high-risk) |
| **2 Aug 2026** | Remainder of Act applies (except Art. 6(1)) |
| **2 Aug 2027** | Art. 6(1) applies (product safety component rule) |
| **Ongoing from 2025** | Art. 7 delegated acts can amend Annex III (add or remove high-risk categories) |
| **2 Aug 2028+** | Commission reviews Annex III every 4 years |

The Commission's Art. 6(5) guidelines (due 2 Feb 2026) are critical - they will provide concrete examples of when AI agents are/are not high-risk.

#### 3.1.6 Penalties Structure (Article 99)

**Effective from:** 2 August 2025

| Violation Type | Max Fine | Max % of Annual Turnover |
|--|--|--|
| Prohibited AI practices (Art. 5) | 35,000,000 EUR | 7% |
| Provider/deployer/notified body obligations (Art. 12, 14, 16, 22, 23, 24, 26, 31, 33, 34, 50) | 15,000,000 EUR | 3% |
| Incorrect/misleading information | 7,500,000 EUR | 1% |

**For SMEs:** Lower fines apply (whichever is lower of the amount or percentage).

**Mitigating factors (Art. 99(7)):**
- Nature, gravity, duration
- Number of affected persons
- Cooperation with authorities
- Degree of responsibility
- Technical/organisational measures implemented
- Whether infringement was notified by operator
- Actions taken to mitigate harm

#### 3.1.7 Implementation Timeline Summary

| Date | Milestone |
|--|--|
| 1 Aug 2024 | Entry into force |
| 2 Feb 2025 | Prohibitions (Art. 5) + AI literacy (Art. 4) apply |
| 2 May 2025 | Codes of practice ready |
| 2 Aug 2025 | Notified bodies, GPAI models, governance, penalties apply |
| **2 Feb 2026** | Commission Art. 6 guidelines due |
| **2 Aug 2026** | Main body (incl. Art. 12, 14, 26, 27, Annex III) applies |
| 2 Aug 2027 | Art. 6(1) product safety rule applies |
| 31 Dec 2030 | Large-scale IT systems compliance deadline |

--

### 3.2 ISO/IEC 42001:2023 (AIMS)

#### 3.2.1 Standard Overview

- **Published:** December 2023
- **Scope:** Information technology - Artificial intelligence - Management system
- **Committee:** ISO/IEC JTC 1/SC 42 (Artificial intelligence)
- **Pages:** 51
- **Annex structure:** Uses High-Level Structure (HLS) aligned with ISO 27001, ISO 9001, ISO 14001

**Current status:** Published (Stage 60.60), 1st Edition. Currently listed as a harmonised standard candidate for the EU AI Act.

#### 3.2.2 Key Clauses Mapped to Agent Lifecycle

| ISO 42001 Clause | Content | Agent Lifecycle Mapping |
|--|--|--|
| **4. Context** | Understanding org context, stakeholder needs, scope | Define agent deployment context, regulatory environment |
| **5. Leadership** | AI policy, roles, responsibilities | Agent governance policy; CISO/DPO roles for agent oversight |
| **6. Planning** | AI risk assessment, AI risk treatment, objectives | Agent risk assessment (prompt injection, tool misuse, data leakage); treatment plan |
| **7. Support** | Resources, competence, awareness, communication | Agent operator training; AI literacy (aligned with Art. 4) |
| **8. Operation** | Planning & control, AI risk treatment, AI system impact assessment | Agent deployment controls; impact assessment per use case |
| **9. Evaluation** | Monitoring, internal audit, management review | Agent monitoring; automated guardrails; periodic review |
| **10. Improvement** | Nonconformity, corrective action, continual improvement | Agent incident response; model retraining; guardrail updates |

#### 3.2.3 Key AIMS Requirements for Agent Systems

1. **AI Policy (Clause 5.2):** Must define principles for responsible AI agent development/deployment
2. **AI Risk Assessment (Clause 6.1):** Must assess risks specific to autonomous agent behaviour
3. **AI System Impact Assessment (Clause 6.1.6):** Requires documented impact assessment per agent system - aligns with Art. 27 FRIA
4. **Objectives (Clause 6.2):** Measurable objectives for agent governance
5. **Documented Information (Clause 7.5):** Evidence of all processes - agent logs, decisions, risk assessments
6. **Operational Planning (Clause 8.1):** Controls for agent development, testing, deployment
7. **AI Risk Treatment (Clause 8.2):** Controls to mitigate agent-specific risks
8. **Monitoring (Clause 9.1):** Continuous monitoring of agent behaviour

#### 3.2.4 Integration with ISO/IEC 27001 (ISMS)

ISO offers a package: ISO/IEC 42001 + ISO/IEC 27001 at 10% discount (CHF 380 for both).

**Integration points:**

| Area | ISO 27001 Control | ISO 42001 Mapping |
|--|--|--|
| Asset management | A.5.9 | Agent model inventory |
| Access control | A.8 | Agent API key mgmt, tool access |
| Cryptography | A.6 | Agent communication encryption |
| Physical security | A.7 | Infrastructure hosting agents |
| Operations security | A.8 | Agent runtime monitoring |
| Communications security | A.8 | Agent-tool API security |
| Supplier relationships | A.15 | Third-party model provider mgmt |
| Incident management | A.16 | Agent incident response |
| Business continuity | A.17 | Agent redundancy/failover |

**AMI-Agents recommendation:** Run AIMS + ISMS as integrated management system. The Plan-Do-Check-Act cycle applies identically.

#### 3.2.5 Certification Process

1. **Gap analysis** (internal or third-party)
2. **Documentation review** - AI policy, risk assessment, impact assessments, procedures
3. **Stage 1 audit** - Readiness review (on-site or remote)
4. **Stage 2 audit** - Implementation effectiveness (on-site)
5. **Certification decision** - Valid for 3 years
6. **Surveillance audits** - Annual
7. **Recertification** - Every 3 years

**Estimated timeline:** 6-12 months from readiness to certification for mature organisations.

**Accredited certification bodies:** Currently limited but growing (BSI, SGS, TUV, DNV have announced AIMS certification services).

#### 3.2.6 Harmonised Standard Status with EU AI Act

- ISO/IEC 42001 is **not yet formally listed** in the Official Journal as a harmonised standard under the EU AI Act
- CEN-CENELEC is working on parallel adoption (expected EN ISO/IEC 42001)
- When adopted as harmonised, compliance with ISO 42001 will provide **presumption of conformity** with relevant AI Act requirements
- The standard is cited in EU AI Act recitals and guidance as a benchmark

--

### 3.3 NIST AI RMF + NIST AI 600-1

#### 3.3.1 NIST AI RMF 1.0 Overview

**Published:** January 2023
**Updated:** 2025 (playbook and guidance)
**Status after EO 14110 rescission:** The Executive Order on Safe, Secure, and Trustworthy AI (Oct 2023) was rescinded on 20 Jan 2025. However, NIST continues AI RMF work under its statutory authority and through the new **CAISI** (Center for AI Standards and Innovation). The **White House AI Action Plan** (July 2025) names NIST extensively.

**Core Functions applied to Agentic AI:**

| Function | Purpose | Agent-Specific Application |
|--|--|--|
| **GOVERN** | Culture of risk management | Agent governance policy, oversight structure, accountability framework |
| **MAP** | Context understanding | Map agent capabilities, tool integrations, data flows, stakeholder impact |
| **MEASURE** | Risk identification | Measure agent-specific risks: hallucination, tool misuse, data leakage, excessive agency |
| **MANAGE** | Risk treatment | Implement guardrails, monitoring, human-in-loop, incident response |

#### 3.3.2 NIST AI 600-1 - Generative AI Profile

**Published:** July 2024

**Key agent-relevant controls from the GenAI profile:**

- **GOVERN 1.1:** Establish AI risk management roles - includes agent-specific oversight
- **GOVERN 2.1:** Document AI system purpose - document what the agent can/cannot do
- **GOVERN 4.1:** Third-party model vetting - crucial for foundation model agents
- **MAP 1.1:** Intended purpose - agent use case boundaries
- **MAP 2.1:** Critical characteristics - agent autonomy level, tool access scope
- **MAP 3.1:** Risk taxonomy - agent-specific risks (jailbreaks, tool misuse, cascading failures)
- **MEASURE 1.1:** Testability - agent behaviour testing, red-teaming
- **MEASURE 2.3:** Bias measurement - agent decision-making bias
- **MANAGE 3.1:** Monitoring - real-time agent behaviour monitoring
- **MANAGE 4.1:** Incident response - agent failure scenarios

The GenAI profile **directly addresses agent-specific risks** via actions related to:
- "system or tool use"
- "delegation of tasks"
- "autonomous operation"
- "chaining of model outputs"

#### 3.3.3 NIST AI Agent Test Suite (Announced)

NIST announced an AI Agent Test Suite via CAISI in Q4 2026. This will include:
- Agent behaviour evaluation benchmarks
- Multi-step reasoning accuracy tests
- Tool use safety evaluations
- Agentic workflow robustness testing

**Related NIST initiatives:**
- **NIST GenAI** program - evaluation of generative AI including agent systems
- **TEVV** (Test, Evaluation, Validation, Verification) - framework applied to autonomous systems
- **AI Risk Management Framework** - currently the most widely adopted voluntary framework globally

#### 3.3.4 Secure AI Development (Secure by Design for AI)

NIST's secure-by-design principles applied to AI agents:
1. **Secure design:** Agent architecture with least privilege, sandboxing tool execution
2. **Secure development:** Supply chain security for model weights, prompt templates, tool definitions
3. **Secure deployment:** API security, authentication, rate limiting for agent endpoints
4. **Secure operation:** Monitoring for prompt injection, anomalous tool calls, data exfiltration

--

### 3.4 OWASP / ETSI / CEN-CENELEC

#### 3.4.1 OWASP Top 10 for LLM Applications

**Current version:** v2025 (superseded v1.1)

**Agent-relevant entries (v1.1 and v2025):**

| OWASP Entry | Agent Relevance | AMI Mitigation |
|--|--|--|
| **LLM01: Prompt Injection** | **CRITICAL** - direct/indirect injection into agent prompts | Guardrails for input sanitisation, context isolation |
| **LLM02: Insecure Output Handling** | Agent outputs that execute code or make API calls | Output validation before tool execution |
| **LLM04: Model DoS** | Recursive agent loops causing cost blowout | Budget limits, recursion depth limits |
| **LLM05: Supply Chain** | Third-party model and tool vulnerabilities | SBOM for agents, vendor assessment |
| **LLM06: Sensitive Info Disclosure** | Agent leaking data in responses | Context filtering, PII redaction |
| **LLM07: Insecure Plugin Design** | **CRITICAL** - tool/plugin security for agents | Tool access control, input validation per tool |
| **LLM08: Excessive Agency** | **CRITICAL** - agents with unchecked autonomy | Scope boundaries, approval gates, human-in-loop |
| **LLM09: Overreliance** | Humans overly trusting agent outputs | Confidence scoring, verification prompts |

**OWASP GenAI Security Project (2025+):**
- Expanded beyond Top 10 to cover agentic AI security
- Over 600 contributing experts from 18+ countries
- Agents are now a **first-class category** in the project's scope
- Work includes: Agent security testing methodology, agent threat modelling guide

#### 3.4.2 ETSI SAI (Securing Artificial Intelligence)

**Industry Specification Group (ISG):**
- **SAI-001:** AI Security Process Framework - defines AI security lifecycle including autonomous systems
- **SAI-002:** AI Threat Mitigation - mitigation catalogue for AI threats
- **SAI-005:** AI Security Testing - testing methodology applicable to agents

**Agent relevance:**
- SAI-001 identifies autonomous decision-making as a distinct risk category
- SAI-002 includes specific mitigations for AI agent tool misuse
- SAI-005 testing methodology can be applied to agent behaviour testing

#### 3.4.3 CEN-CENELEC JTC 21 (AI Standards Pipeline)

**Committee:** Joint Technical Committee 21 - Artificial Intelligence

**Key deliverables for EU AI Act harmonisation:**

| Standard | Status | Scope | Agent Relevance |
|--|--|--|--|
| **prEN ISO/IEC 42001** | Under adoption (EN version of ISO 42001) | AIMS requirements | Management system for agent operations |
| **prEN ISO/IEC 23894** | Under adoption | AI risk management | Agent risk assessment methodology |
| **prEN ISO/IEC 42005** | Published 2025 | AI impact assessment | Agent deployment impact assessment |
| **Various AI Act mandates** | In development | Risk mgmt, logging, transparency, accuracy | Technical specifications aligned with Art. 9, 12, 13, 15 |

**EU AI Act harmonised standards mandates (issued to CEN-CENELEC):**
1. Risk management system (Art. 9)
2. Data governance (Art. 10)
3. Technical documentation (Art. 11)
4. **Record-keeping / logging (Art. 12)** - directly affects agent systems
5. Transparency (Art. 13)
6. Human oversight (Art. 14) - agent override/stop requirements
7. Accuracy, robustness, cybersecurity (Art. 15)

**Expected timeline:** First harmonised standards expected **late 2026 to early 2027**. Until published, providers must use alternative conformity routes (self-assessment or common specifications).

--

### 3.5 DORA / NIS2 / GDPR

#### 3.5.1 DORA (Digital Operational Resilience Act)

**Effective from:** 17 January 2025 (full application)

**Applicability:** Financial entities (banks, investment firms, payment institutions, crypto-asset service providers)

**Agent-relevant requirements:**

| DORA Article | Requirement | Agent Implication |
|--|--|--|
| **Art. 5-16** | ICT Risk Management Framework | Agent systems must be covered by ICT risk policy |
| **Art. 7** | ICT Systems Protection | Agent API security, authentication, encryption |
| **Art. 8** | Identification & Classification | Agent as an ICT asset; classify criticality |
| **Art. 9** | Protection & Prevention | Guardrails for agent operations; access controls |
| **Art. 10** | Detection | Agent monitoring, anomaly detection |
| **Art. 11** | Response & Recovery | Agent failure response plan; rollback capability |
| **Art. 12** | Backup & Restore | Agent state persistence; checkpoint/restore |
| **Art. 17-23** | ICT Incident Reporting | Mandatory reporting of agent incidents; classification by severity |
| **Art. 24-27** | Digital Operational Resilience Testing | Agent penetration testing; red-teaming; TLPT for systemic entities |
| **Art. 28-44** | Third-Party Risk (TPR) | Third-party model providers; tool provider risk |

**Key obligations for agent systems in financial services:**
- Agent use must be included in the ICT risk management framework
- Agent failures are reportable incidents under strict timelines
- Agents using external models trigger third-party risk management

**Cross-regulation with EU AI Act (DORA Recital 29 + AI Act Art. 26(5)):**
- For deployers that are financial institutions, monitoring obligations under Art. 26(5) are fulfilled by complying with internal governance rules under financial services law
- DORA testing requirements (TLPT) may overlap with AI Act conformity assessment

#### 3.5.2 NIS2 (Directive (EU) 2022/2555)

**Effective from:** 17 October 2024 (transposition deadline); Member States have implemented (with staggered enforcement)

**Applicability:** Essential and important entities in energy, transport, banking, health, digital infrastructure, public administration

**Agent-relevant requirements:**

| NIS2 Article | Requirement | Agent Implication |
|--|--|--|
| **Art. 20** | Incident reporting (early warning 24h, notification 72h, final report 1 month) | Agent security incidents must be reported |
| **Art. 21** | Risk management measures | Agent supply chain security; access controls |
| **Art. 22** | Use of cybersecurity products | Agent security tools; encrypted agent communication |
| **Art. 24-28** | Security requirements (supply chain, encryption, access, etc.) | Agent vulnerability management; tool vetting |

**Agent relevance:**
- Agents deployed in critical infrastructure (energy, health, transport) trigger NIS2 obligations
- Supply chain security includes foundation model providers
- Incident reporting timeline at 24h/72h/1 month applies to agent failures that disrupt services

#### 3.5.3 GDPR Article 22 - Automated Decision-Making

**Text of Art. 22(1):**
> The data subject shall have the right not to be subject to a decision based solely on automated processing, including profiling, which produces legal effects concerning him or her or similarly significantly affects him or her.

**Art. 22(2) - Exceptions (only if suitable safeguards in place):**
- (a) Necessary for contract performance
- (b) Authorised by EU/Member State law
- (c) Based on explicit consent

**Art. 22(3) - Safeguards required:**
> At least the right to obtain human intervention on the part of the controller, to express his or her point of view and to contest the decision.

**Art. 22(4):** Special category data cannot be used for automated decisions unless Art. 9(2)(a) or (g) applies.

**Agent-specific implications:**
- If an agent makes a decision **without meaningful human review**, it triggers Art. 22
- This applies to: recruitment agents, credit-scoring agents, benefit-determination agents, insurance-pricing agents
- **"Solely automated"** means no meaningful human involvement - a rubber-stamping human is not sufficient
- The right to human intervention is **mandatory** - AMI agents that make decisions affecting individuals must include a human review pathway
- EDPB Guidelines 8/2022 provide detailed interpretation of "solely automated" and "significant effects"

**Cross-regulation interaction:**
- EU AI Act Art. 86 provides a right to explanation of individual decision-making
- GDPR Art. 22 + AI Act Art. 86 create overlapping rights for individuals affected by agent decisions
- AI Act FRIA (Art. 27) requires deployers to use Art. 13 information to comply with GDPR DPIA obligations

#### 3.5.4 ENISA AI Threat Landscape

The ENISA Threat Landscape 2024 (published Sep 2024) and 2025 (published Oct 2025) identify:
- **AI-specific threats:** Adversarial manipulation (prompt injection), model poisoning, output manipulation
- **Agent-specific concerns:** Cascade failures in multi-agent systems, tool misuse, autonomous decision manipulation
- **Top threats 2025:** DDoS, ransomware, data threats, AI-specific attacks rising sharply

ENISA's work on AI cybersecurity includes sectorial threat landscapes for AI systems, with specific attention to autonomous decision-making systems.

--

### 3.6 MLCommons AI Safety

#### 3.6.1 Overview

MLCommons is an open engineering consortium that manages the AI Safety benchmark suite.

**Current status:**
- **AI Safety v1.0** - first safety benchmark results published March 2025
- Covers: hazardous behaviour categories (chemical, biological, cyber, autonomous replication, etc.)
- Tests model refusal patterns across risk categories

**Working groups:**
- **AI Safety Working Group** - benchmark design, data curation
- **Agents Working Group** (newer) - developing agent-specific safety evaluations
- Participants include: Google, OpenAI, Anthropic, Meta, Microsoft, NVIDIA, various academic institutions

#### 3.6.2 Agent-Specific Safety Testing

The MLCommons Agents WG is developing:
- Multi-turn conversation safety tests
- Tool use safety benchmarks
- Autonomous decision boundary tests
- Delegation safety evaluations

**Status:** In development - no official agent safety benchmark released yet.

#### 3.6.3 Frontier Model Forum

The Frontier Model Forum commitments include:
- Safety testing of frontier AI systems (including agent capabilities)
- Red-teaming collaboration
- Information sharing on safety incidents
- Support for MLCommons benchmarks

--

## 4. Gap Analysis: AMI-Agents vs Requirements

| Regulation | AMI Current Status | Gaps | Priority | Remediation Path |
|--|--|--|--|--|
| **EU AI Act Art. 12** (Auto Logging) | 0 - No evidence of automatic logging system | No immutable audit trail; no lifecycle logging capability | **Critical** | Implement agent audit logging module: all tool calls, decisions, state changes, human overrides |
| **EU AI Act Art. 14** (Human Oversight) | 1 - Human-in-loop patterns exist | No documented 'stop button' architecture; no override design pattern | **Critical** | Design and implement interrupt/override/stop mechanism with safe state halting |
| **EU AI Act Art. 26** (Deployer Duties) | 0 - No deployer compliance framework | No log retention policy (6 month min); no worker notification process; no suspension protocol | **Critical** | Build deployer compliance toolkit; log retention system; notification templates |
| **EU AI Act Art. 6 / Annex III** (Classification) | 0 - No classification assessments | No documented assessment per agent use case; no register of high-risk systems | **High** | Create classification documentation for each agent type; file with EU database if high-risk |
| **ISO/IEC 42001:2023** (AIMS) | 1 - Referenced as target | No AI policy; no AI risk assessment; no impact assessment process; no management system documentation | **High** | Implement AIMS aligned with ISO 42001 + ISO 27001 integrated management system |
| **ISO/IEC 27001:2022** (ISMS) | 2 - Partial security controls | No ISO-aligned ISMS; no Annex A mapping | **High** | Implement ISMS; achieve certification (prerequisite for AIMS) |
| **NIST AI RMF** (Govern/Map/Measure/Manage) | 1 - Referenced as target | No systematic risk assessment against RMF functions; no GenAI profile mapping | **Medium** | Perform RMF-based risk assessment; document in AI governance docs |
| **OWASP LLM Top 10** | 1 - Some guardrails in place | No systematic mapping against LLM01-LLM10; excessive agency (LLM08) not addressed | **High** | Map AMI to OWASP; mitigate LLM08 (excessive agency) as priority |
| **DORA** (ICT Risk) | 0 - Not assessed | No ICT risk classification of agents; no incident reporting compliance | **Medium** | If deploying in financial sector: DORA compliance program |
| **NIS2** (Incident Reporting) | 0 - Not assessed | No 24h/72h incident reporting pipeline | **Medium** | Implement incident classification and reporting workflow |
| **GDPR Art. 22** | 1 - Human review exists | No documented Art. 22 compliance for agent decisions | **High** | Assess each agent use case for "solely automated decision-making" triggers |
| **CEN-CENELEC standards** | 0 - Not tracked | No monitoring of harmonised standard development | **Medium** | Assign standards monitoring; prepare for conformity assessment |
| **MLCommons AI Safety** | 0 - Not engaged | No safety benchmark participation | **Low** | Monitor agent safety benchmark development; adopt when stable |

--

## 5. Certification Roadmap Recommendations

### Phase 1: Foundation (Q3-Q4 2026)
1. **ISO/IEC 27001:2022** certification - prerequisite for AIMS
2. Implement **agent audit logging** (EU AI Act Art. 12 compliance)
3. Build **human oversight architecture** with stop button (Art. 14)
4. Create **high-risk classification** documentation per agent use case
5. Document **OWASP LLM Top 10** mitigation mappings

### Phase 2: AIMS Implementation (Q1-Q2 2027)
1. Develop **AI policy** and governance framework
2. Implement **AI risk assessment** process per ISO 42001 Clause 6.1
3. Conduct **AI system impact assessments** per agent use case
4. Establish **monitoring and evaluation** (Clause 9)
5. Achieve **ISO/IEC 42001:2023** certification

### Phase 3: Regulatory Alignment (Q3 2027-Q2 2028)
1. Prepare for **EU AI Act** conformity assessment (Art. 43)
2. Register high-risk systems in **EU database** (Art. 49, 71)
3. Align with **CEN-CENELEC** harmonised standards (once published)
4. Implement **DORA** compliance (if financial sector)
5. Implement **NIS2** incident reporting

### Phase 4: Continuous Compliance (Ongoing)
1. Annual ISO surveillance audits
2. Monitor delegated acts and Annex III amendments
3. Participate in **MLCommons** agent safety benchmarks
4. Track **NIST** agent test suite results
5. Regular **OWASP** reassessment

--

## 6. Sources Consulted

### Primary Legal Sources
1. Regulation (EU) 2024/1689 - EU AI Act (Official Journal, 13 June 2024)
   - Articles 6, 12, 14, 26, 99, 113 (via artificialintelligenceact.eu)
   - Annex III (High-Risk Classification)
   - Implementation Timeline
2. GDPR Art. 22 - Automated individual decision-making (gdpr-info.eu)
3. Directive (EU) 2022/2555 - NIS2
4. Regulation (EU) 2022/2554 - DORA

### Standards Sources
5. ISO/IEC 42001:2023 - AIMS (iso.org)
6. ISO/IEC 27001:2022 - ISMS (iso.org)
7. NIST AI RMF 1.0 (nist.gov)
8. NIST AI 600-1 GenAI Profile (nist.gov)

### Industry Guidance
9. OWASP Top 10 for LLM Applications v1.1 / v2025 (owasp.org)
10. OWASP GenAI Security Project (genai.owasp.org)
11. ENISA Threat Landscape 2024, 2025 (enisa.europa.eu)

### Research Organisations
12. Future of Life Institute - EU AI Act resources (artificialintelligenceact.eu)
13. Intersoft Consulting - GDPR commentary (gdpr-info.eu)

--

## 7. Key Takeaways

### For Architecture
1. **LOGGING IS NOT OPTIONAL** - EU AI Act Art. 12 requires automatic logging over the full agent lifecycle. You need an immutable audit trail for every tool call, decision, state transition, and human override.
2. **STOP BUTTON IS MANDATORY** - Art. 14(4)(e) requires a mechanism to interrupt the system through a 'stop' button or procedure that brings the system to a halt in a safe state. This is hard requirements for high-risk agent systems.
3. **HUMAN OVERRIDE IS THE LAW** - The right to override, disregard, or reverse automated agent decisions is mandated by both EU AI Act Art. 14(4)(d) and GDPR Art. 22(3).

### For Compliance
4. **ASSUME HIGH-RISK UNLESS PROVEN OTHERWISE** - Any agent making decisions in employment, credit, education, or essential services (Annex III categories 3-5) is automatically high-risk unless it passes the narrow procedural task derogation. Document the decision.
5. **AIMS + ISMS INTEGRATION** - ISO 42001 and ISO 27001 are designed to work together. Run them as an integrated management system. The EU AI Act will reference harmonised standards built on these frameworks.
6. **LOGS FOR 6+ MONTHS** - Art. 26(6) requires deployers to keep logs for at least 6 months. Build your storage and retention architecture accordingly.

### For Penalty Exposure
7. **15M EUR OR 3% OF TURNOVER** - Non-compliance with Art. 12, 14, or 26 can result in fines up to 15M EUR or 3% of worldwide annual turnover. This applies to both providers AND deployers.
8. **35M EUR FOR PROHIBITED PRACTICES** - If an agent engages in prohibited practices (Art. 5), the fine is 35M EUR or 7% of turnover.

### For Certification Roadmap
9. **ISO 27001 FIRST, THEN 42001** - Get ISMS certified first (prerequisite capability for AIMS).
10. **MONITOR CEN-CENELEC HARMONISED STANDARDS** - First harmonised standards expected late 2026 to early 2027. These will define the technical specifications for logging, oversight, and risk management.
11. **CEN-CENELEC JTC 21** is the committee to watch for EU AI Act technical specifications.

### For Monitoring
12. **NIST AI AGENT TEST SUITE (Q4 2026)** - This will define US government evaluation methodology for agents.
13. **MLCOMMONS AGENTS WG** - Agent-specific safety benchmarks under development.
14. **EU COMMISSION ART. 6 GUIDELINES (2 FEB 2026)** - Critical guidance on when agents are/aren't high-risk.
15. **OWASP AGENTIC AI** - Agents are now a first-class category in the OWASP GenAI Security Project; expect agent-specific threat taxonomies.
