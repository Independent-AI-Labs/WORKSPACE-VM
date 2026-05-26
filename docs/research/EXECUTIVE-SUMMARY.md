# Executive Summary — Agentic Guardrails, Compliance, Standardisation & Security

> **Research programme covering 7 workstreams, 4,435+ lines of analysis, 84 academic papers, 25+ real-world incidents, 7 FAANG vendors, 15+ startups, 12 neocloud providers, and 5 major regulatory frameworks.**
> Status: **COMPLETE** | Last updated: 2026-05-26

---

## The Bottom Line

Enterprise AI agent deployment is accelerating faster than the security and compliance infrastructure needed to support it. The EU AI Act's high-risk provisions take full effect on **2 August 2026** — approximately 10 weeks from now. Prompt injection attacks have surged 340% year-over-year and are present in 73% of production agent deployments. No end-to-end solution for agent security exists. The market is fragmented across guardrails, orchestration, observability, security tooling, and compliance — forcing enterprises to integrate 3–5 tools for a complete safety posture.

The window to build the agent security platform is open but finite. Every major incident — PocketOS (production database deleted in 9 seconds), Kiro (AWS environment destroyed), Claude Code (27M token infinite loop) — validates the problem space. Every month without a unified, certifiable, cross-layer solution narrows the opportunity.

---

## 1. Research Scope

Seven workstreams executed in parallel across four phases:

| WS | Title | Focus | Lines |
|----|-------|-------|-------|
| [WS-1](WS-1-FAANG-GUARDRAILS.md) | FAANG & Big Tech | Guardrails from Google, Microsoft, AWS, Meta, Apple, OpenAI, Anthropic | 601 |
| [WS-2](WS-2-SME-ECOSYSTEM.md) | SME & Startup Ecosystem | Guardrails AI, NeMo, LangChain, CrewAI, AutoGen, Semantic Kernel, Arize, Galileo, Lakera, Protect AI, EU startups | 1,100 |
| [WS-3](WS-3-NEOCLOUD-LANDSCAPE.md) | Neocloud Landscape | CoreWeave, Lambda, RunPod, Vast, Together, Fireworks, Modal, Beam, Akash, Golem, Spheron, EU neoclouds | 896 |
| [WS-4](WS-4-REGULATORY-DEEP-DIVE.md) | Standards & Regulation | EU AI Act Art. 12/14/26, ISO 42001, NIST AI RMF, OWASP, DORA, NIS2, GDPR Art. 22 | 711 |
| [WS-5](WS-5-ACADEMIC-LANDSCAPE.md) | Academic Landscape | 84 papers on reward hacking, prompt injection, memory poisoning, sandbox isolation, A2A security, formal verification | 769 |
| [WS-6](WS-6-INCIDENTS-AND-MILESTONES.md) | Incidents & Milestones | 25+ real-world incidents, benchmark analysis, government reports, legal precedents, supply chain attacks | 358 |
| [WS-7](WS-7-SYNTHESIS-AND-STRATEGY.md) | Synthesis & Strategy | Cross-cutting gap analysis, competitive matrix, 18-month roadmap, threat landscape 2026–2028 | 2,076 |
| **Total** | | | **6,511** |

---

## 2. Key Findings by Domain

### 2.1 FAANG Guardrails ([WS-1](WS-1-FAANG-GUARDRAILS.md))

Every major AI vendor now offers agent guardrails, but each is **platform-locked**:

- **[Google/DeepMind](https://cloud.google.com/security-command-center/docs/model-armor-overview)**: Most comprehensive stack — 5-layer safety architecture (Model Armor, Gemini-as-Filter, jailbreak classifier, Agent Gateway with cryptographic IAM per agent, Agent Registry). Project Mariner uses a separate User Alignment Critic model to vet every action before execution. FSF third iteration with Critical Capability Levels. Vertex AI Agent Builder with configurable content filters, grounding, and DLP integration.
- **[Microsoft](https://learn.microsoft.com/en-us/microsoft-copilot-studio/security-and-governance)**: Copilot Studio with XPIA/UPIA real-time protection, Agent 365 control plane (GA May 2026), Purview AI Hub for centralized governance. AutoGen is in maintenance mode — Microsoft Agent Framework (MAF) is the successor with middleware pipeline, Entra Agent ID, and Prompt Shields.
- **[AWS](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-components.html)**: Bedrock Guardrails with content filters, denied topics, word filters, PII detection, contextual grounding checks, and automated reasoning checks. Standard tier (2025) adds 60+ languages and code-domain filtering. Model-agnostic via ApplyGuardrail API.
- **[Meta](https://github.com/meta-llama/PurpleLlama)**: Purple Llama framework with Llama Guard 4 (multimodal, MLCommons hazards taxonomy), Prompt Guard 2 (BERT-style jailbreak detection), Code Shield (static analysis), and LlamaFirewall (unified policy engine with AlignmentCheck for chain-of-thought auditing). Most open of the FAANG group.
- **[Apple](https://security.apple.com/blog/private-cloud-compute/)**: On-device processing eliminates data transfer concerns. Private Cloud Compute with verifiable transparency — stateless, no SSH, Secure Boot, end-to-end encryption. App Intents framework prevents arbitrary code execution. Prefers privacy architecture over detection-based guardrails.
- **[OpenAI](https://platform.openai.com/docs/guides/safety-best-practices)**: Agent SDK with three guardrail types (Input, Output, Tool), `needsApproval` flag for human-in-the-loop, SandboxAgent (beta Apr 2026) with manifest-based workspace contracts. Instruction hierarchy platform-level > developer > user. Safety Reasoner for dynamic step-wise evaluations.
- **[Anthropic](https://docs.anthropic.com/en/docs/build-with-claude/guardrails)**: Constitutional Classifiers++ with two-stage cascade — 95%+ jailbreak blocked, 0.05% over-refusal rate. Permission policies per tool (`always_allow/always_ask/block`). MCP donated to Linux Foundation Agentic AI Foundation. Plan Mode for human approval before execution.

**Strategic insight ([full analysis](WS-1-FAANG-GUARDRAILS.md))**: FAANG provides powerful but platform-locked guardrails. No vendor offers a cross-platform, certifiable security layer. This is the market gap.

### 2.2 SME & Startup Ecosystem ([WS-2](WS-2-SME-ECOSYSTEM.md))

The startup landscape is fragmented across five categories with no single end-to-end solution:

- **Guardrails frameworks**: [NVIDIA NeMo Guardrails](https://docs.nvidia.com/nemo/microservices/latest/guardrails) leads with tool rails and dialog rails via Colang DSL — the only startup with agent-specific action-level interception. [Guardrails AI](https://docs.guardrails.io) has the largest validator marketplace (Hub) but no agent-specific primitives.
- **Orchestration frameworks**: [Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel) has the strongest built-in safety filter system (3 filter types — function invocation, prompt rendering, auto function invocation). LangChain/LangGraph relies on external governance middleware. CrewAI and AutoGen have minimal security defaults.
- **Observability**: [Arize Phoenix](https://arize.com/phoenix) leads with OTEL-native agent traces and AgentEvals. [Galileo](https://galileo.ai/products) (being acquired by Cisco) offers purpose-built agent metrics. WhyLabs and W&B are retrofitted from ML monitoring.
- **Security tooling**: [Lakera](https://lakera.ai) leads prompt injection detection ([95.22% PINT benchmark](https://github.com/lakeraai/pint-benchmark)). Protect AI (acquired by Palo Alto Networks) focuses on ML supply chain. Prompt Security (acquired by SentinelOne) covers AI SPM.
- **EU startups**: [Mistral](https://mistral.ai) (ISO 27001, GDPR-native, EU-hosted), Aleph Alpha (acquired by Cohere, alpha ONE datacenter), and [Deepset](https://deepset.ai) (Haystack, modular pipelines) focus on sovereign foundation models and orchestration — **none offer dedicated agent guardrail products**.

**Key takeaway ([full analysis](WS-2-SME-ECOSYSTEM.md))**: No single tool covers guardrails + orchestration + observability + security. Enterprises need 3–5 integrated tools. European startups are absent from the agent security category.

### 2.3 Neocloud Landscape ([WS-3](WS-3-NEOCLOUD-LANDSCAPE.md))

The infrastructure layer is mature enough for enterprise agent workloads but offers **zero agent-specific security**:

| Tier | Providers | Certification Profile | Agent Security |
|------|-----------|---------------------|----------------|
| **Tier 1: Enterprise-ready** | CoreWeave, Fireworks AI, Lambda Labs | SOC 2 + ISO 27001 + HIPAA (Fireworks: ISO 42001) | None |
| **Tier 2: Growing compliance** | Together AI, RunPod, Modal, Beam | SOC 2 + HIPAA (varies) | gVisor sandbox only |
| **Tier 3: Dev/experimental** | Vast.ai, Replicate, Akash, Golem, Spheron | SOC 2 or partner-level | Marketplace model |

- **[CoreWeave](https://docs.coreweave.com/security/architecture)** leads on every axis: bare metal + DPU isolation, SOC 2 + ISO 27001 + HIPAA, multi-region EU data centres (UK, Sweden, Norway, Spain), NVIDIA CC for GPU TEE, full VPC/SSO/SIEM.
- **[Fireworks AI](https://trust.fireworks.ai)** uniquely holds ISO 42001 (AI Management System) plus SOC 2, ISO 27001/27701, HIPAA, and BYOC/airgapped deployment.
- **[Modal](https://modal.com/docs/guide/security)** and **[Beam](https://trust.beam.org)** provide gVisor sandboxing for untrusted code execution — the closest approximation to agent-specific infrastructure.
- **European neoclouds** ([Scaleway](https://www.scaleway.com), [Hetzner](https://www.hetzner.com), [OVHcloud](https://www.ovhcloud.com), Ionos, Exoscale, Leaseweb) offer sovereign infrastructure with strong certifications (SecNumCloud, C5) but limited GPU catalogues and no agent-level features.

**Strategic insight**: Neoclouds provide the substrate. The agent security layer that runs on that substrate does not yet exist as a standalone product.

### 2.4 Regulatory Landscape ([WS-4](WS-4-REGULATORY-DEEP-DIVE.md))

The regulatory environment presents both existential risk and strategic opportunity:

**EU AI Act — Hard deadline 2 August 2026:**
- **[Article 12](https://artificialintelligenceact.eu/article/12/) (Automatic Logging)**: High-risk AI systems must automatically record events over their lifetime. Logs must be retained for at least 6 months. Current mutable session transcripts do not comply.
- **[Article 14](https://artificialintelligenceact.eu/article/14/) (Human Oversight)**: Mandatory stop button mechanism, override/reverse capability, and automation bias awareness measures. Not optional — a legal requirement.
- **[Article 26](https://artificialintelligenceact.eu/article/26/) (Deployer Duties)**: Log retention, worker notification, suspension protocol, input data quality — all deployer obligations that AMI must enable.
- **[Annex III](https://artificialintelligenceact.eu/annex/3/) (High-Risk Classification)**: Agents in employment, education, essential services, credit, insurance, and law enforcement are automatically high-risk unless they pass the narrow procedural task derogation. Profiling agents are ALWAYS high-risk.
- **Penalties**: Up to 35M EUR or 7% of global annual turnover for prohibited practices; 15M EUR or 3% for Article 12–26 violations.

**Other frameworks:**
- **[ISO/IEC 42001:2023](https://www.iso.org/standard/81230.html) (AIMS)**: AI management system certification. Available now. Provides EU AI Act conformity presumption when adopted as harmonised standard. No AMI-affiliated system holds it.
- **[NIST AI RMF 1.0](https://www.nist.gov/itl/ai-risk-management-framework) + [GenAI Profile](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958388)**: Most widely adopted voluntary framework globally. Agent-specific controls for tool use, delegation, and autonomous operation. NIST AI Agent Test Suite announced for Q4 2026.
- **[OWASP LLM Top 10](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/)**: Excessive Agency (LLM06) is the systemic failure mode — the root cause of PocketOS, Kiro, and Claude Code incidents. Updated [OWASP Agentic Top 10](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) published December 2025.
- **[GDPR Article 22](https://gdpr-info.eu/art-22-gdpr/)**: Right not to be subject to solely automated decisions. [Schufa (ECJ C-634/21, Dec 2023)](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:62021CJ0634) and [AMS Austria (BVwG, Sep 2025)](https://www.fwp.at/en/news/blog/recent-federal-administrative-court-decision-on-human-influence-in-exclusively-automated-decisions-under-article-22-gdpr-in-the-case-of-the-ams) establish rigorous standards — cursory human review is legally insufficient.
- **[DORA](https://www.esma.europa.eu/esmas-activities/digital-finance-and-innovation/digital-operational-resilience-act-dora) / [NIS2](https://digital-strategy.ec.europa.eu/en/policies/nis2-directive)**: Agent failures in financial services and critical infrastructure trigger mandatory incident reporting (24h/72h/1 month timelines).

**Full regulatory analysis in [WS-4](WS-4-REGULATORY-DEEP-DIVE.md) and [WS-7 Appendix A](WS-7-SYNTHESIS-AND-STRATEGY.md#appendix-a-eu-ai-act-article-by-article-compliance-mapping) (Article-by-Article compliance mapping, gap analysis, certification roadmap).**

### 2.5 Academic Research ([WS-5](WS-5-ACADEMIC-LANDSCAPE.md))

The literature across [84 papers](WS-5-ACADEMIC-LANDSCAPE.md#2-annotated-bibliography) at top venues converges on five architectural conclusions:

| Finding | Source Papers | Strategic Implication |
|---------|--------------|----------------------|
| **Prompt injection is structurally inescapable** | [27](https://arxiv.org/abs/2605.17634), [19](https://proceedings.mlr.press/v235/wolf24a.html), [26](https://arxiv.org/abs/2503.0061) | Containment (semantic virtualization) is the only viable strategy. Prevention is not achievable at the token level. |
| **Reward hacking is an equilibrium, not a bug** | [2](https://arxiv.org/abs/2603.28063), [3](https://arxiv.org/abs/2604.15149), [19](https://proceedings.mlr.press/v235/wolf24a.html) | Architect for detection and mitigation, not prevention. Embed hack-verifiable properties in environments. |
| **Memory poisoning enables persistent cross-session compromise** | [33–40](WS-5-ACADEMIC-LANDSCAPE.md#2-2-adversarial-robustness) | MINJA achieves 95%+ injection with query-only access. Zombie Agent persists across sessions. Cryptographic integrity mandatory. |
| **Adaptive attacks bypass all current defences** | [26](https://arxiv.org/abs/2503.0061), [27](https://arxiv.org/abs/2605.17634), [28](https://arxiv.org/abs/2509.22830) | Heuristic detection is insufficient. Structural separation required. |
| **Formal runtime verification provides provable guarantees** | [73](https://arxiv.org/abs/2603.20356), [75](https://arxiv.org/abs/2507.08270), [77](https://arxiv.org/abs/2510.05156), [78](https://arxiv.org/abs/2512.23738), [81](https://proceedings.mlr.press/v267/chen25a.html) | AgentSpec (ICSE 2026) achieves 90%+ detection. ShieldAgent (ICML 2025) achieves 90.1% recall with 64.7% fewer API queries. |
| **TEE + Confidential GPU provides hardware-rooted isolation** | [44](https://arxiv.org/abs/2512.05951), [45](https://arxiv.org/abs/2605.03213), [46](https://arxiv.org/abs/2507.02770), [54](https://docs.nvidia.com/confidential-computing/) | Omega TAP (arXiv 2512.05951) shows production-ready trusted agent runtime. |
| **Semantic virtualization achieves near-zero ASR** | [30](https://arxiv.org/abs/2604.24118) | AgentVisor treats LLM as untrusted Guest mediated by trusted Visor. |
| **Multi-agent delegation poisoning is a new attack surface** | [58–65](WS-5-ACADEMIC-LANDSCAPE.md#2-4-a2a-multi-agent-security) | G-Safeguard is the first paper on circular delegation detection. Multi-agent security is 6–12 months behind single-agent. |

**Full annotated bibliography with 84 papers in [WS-5](WS-5-ACADEMIC-LANDSCAPE.md#2-annotated-bibliography).**

### 2.6 Real-World Incidents ([WS-6](WS-6-INCIDENTS-AND-MILESTONES.md))

The incident landscape confirms the research findings with alarming clarity:

| Incident | Date | Impact | Root Cause |
|----------|------|--------|------------|
| **[PocketOS](https://indianexpress.com/article/technology/artificial-intelligence/how-an-ai-agent-deleted-a-startups-critical-data-10660538/)** | Apr 2026 | Production DB + backups deleted in 9 seconds; 30-hour outage; 3 months data loss | Over-privileged tokens, no confirmation gates, no sandbox |
| **[Kiro (AWS)](https://ubos.tech/news/amazons-ai-coding-assistant-kiro-triggers-major-aws-outage-impact-and-lessons/)** | Dec 2025 | Autonomous agent deleted production AWS environment; 13-hour outage | Unrestricted tool scope |
| **[Claude Code loop](https://github.com/anthropics/claude-code/issues/15909)** | Jan 2026 | 27M tokens consumed in 4.6 hours; $2K+ compute | No timeout, no kill switch |
| **Financial services agent** | Mar 2026 | Internal pricing data leaked for 3 weeks via prompt injection | Undetected prompt injection |
| **[Shai-Hulud worm](https://labs.cloudsecurityalliance.org/research/csa-research-note-shai-hulud-npm-worm-ai-developer-supply-ch/)** | Sep 2025/May 2026 | 40+ npm packages; self-spreading malware targeting MCP servers | Protocol-level MCP insecurity |
| **[Gemini CLI CVSS-10](https://www.securityweek.com/critical-gemini-cli-flaw-enabled-host-code-execution-supply-chain-attacks/)** | Apr 2026 | Supply chain attack through code dependencies | Indirect injection with no defence |
| **[AUSPEX / TeamPCP](https://labs.cloudsecurityalliance.org/research/csa-research-note-teampcp-cicd-supply-chain-20260325-csa-sty/)** | Jul 2025 | CI token stolen → Kubernetes pivot → 500K records exfiltrated | CI/CD pipeline insecurity |

**Key statistics:**
- AI incidents grew from 149 (2023) to 233 (2024), with 2025–2026 surpassing all prior years combined ([AI Incident Database](https://incidentdatabase.ai/apps/incidents/)).
- 65% of organizations report agent-related incidents ([CSA, Apr 2026](https://cloudsecurityalliance.org/press-releases/2026/04/21/new-cloud-security-alliance-survey-reveals-82-of-enterprises-have-unknown-ai-agents-in-their-environments)).
- Prompt injection surged 340% YoY ([OWASP, Apr 2026](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/)), present in 73% of production deployments.
- 91% of agent deployments are vulnerable to attacks current benchmarks cannot detect ([Stanford/MIT/CMU study, Feb 2026](https://www.bankinfosecurity.com/91-of-ai-agents-vulnerable-to-tool-chaining-attacks-a-26271)).
- Agent security funding exceeded $120M+ in identifiable rounds ([Noma $100M](https://noma.security/noma-security-raises-100m-to-drive-adoption-of-ai-agent-security/), [Trent AI $13M](https://www.businesswire.com/news/home/20260415005301/en/Trent-AI-Raises-13M-Seed)).

**Full incident timeline in [WS-6](WS-6-INCIDENTS-AND-MILESTONES.md). Threat landscape 2026–2028 with attack trees in [WS-7 §5](WS-7-SYNTHESIS-AND-STRATEGY.md#section-5-threat-landscape-2026-2028).**

---

## 3. Comparative Position ([full matrix](WS-7-SYNTHESIS-AND-STRATEGY.md#2-2-dimension-by-dimension-comparison))

AMI-Agents' current state compared to the competitive landscape reveals a clear picture:

| Dimension | FAANG (avg) | Startup (avg) | Neocloud (avg) | AMI Current |
|-----------|:-----------:|:-------------:|:---------------:|:-----------:|
| Agent isolation | 4.5/5 | 2.5/5 | 4.0/5 | **1.5/5** |
| Policy enforcement | 4.5/5 | 3.0/5 | 2.5/5 | **2.5/5** |
| Audit logging | 4.5/5 | 2.5/5 | 3.5/5 | **2.0/5** |
| Human-in-the-loop | 4.0/5 | 2.5/5 | 1.0/5 | **1.5/5** |
| Compliance certifications | 5.0/5 | 2.5/5 | 3.5/5 | **0.0/5** |
| EU data sovereignty | 4.0/5 | 3.0/5 | 4.0/5 | **4.0/5** |
| Prompt injection defence | 4.5/5 | 3.5/5 | 0.0/5 | **0.0/5** |
| Tool-use restrictions | 4.5/5 | 3.0/5 | 0.0/5 | **0.0/5** |
| Agent-to-agent security | 3.0/5 | 1.5/5 | 0.0/5 | **0.0/5** |
| Observability | 4.5/5 | 3.5/5 | 3.0/5 | **1.0/5** |
| Sandbox security | 4.0/5 | 2.5/5 | 4.0/5 | **1.5/5** |
| Runtime guardrails | 4.5/5 | 3.0/5 | 1.0/5 | **1.0/5** |
| **Average** | **4.3/5** | **2.7/5** | **2.2/5** | **1.3/5** |

AMI leads only in EU data sovereignty (tied with neoclouds). The compliance certifications gap (0.0 vs 5.0 for FAANG) is the single most critical weakness.

---

## 4. Strategic Recommendations ([full analysis](WS-7-SYNTHESIS-AND-STRATEGY.md#section-4-strategic-recommendations))

### 4.1 Five Must-Win Battles

| Battle | Target | Timeline | Impact |
|--------|--------|----------|--------|
| **1. EU AI Act Compliance** | Full compliance for high-risk classification, including audit trail, stop button, reversal, and deployer toolkit | **2 Aug 2026** (10 weeks) | Regulatory survival. Without it, cannot sell to EU enterprises. |
| **2. Semantic Virtualization** | Production Guest/Visor split with STI protocol — treat LLM as untrusted | Q3 2026 (2 week MVP) | Structural containment of prompt injection. Near-zero ASR. 6–9 month first-mover advantage. |
| **3. Multi-Agent Security** | Signed A2A protocol with delegation depth tracking, before multi-agent goes mainstream | Q4 2026 | Prevent the next generation of agent attacks. First-mover in undefined category. |
| **4. Certification Trinity** | ISO 27001 (Q1 2027) → SOC 2 Type II (Q3 2027) → ISO 42001 (Q3 2027) | 18 months | Enterprise procurement. ISO 27001 opens doors. SOC 2 keeps them open. ISO 42001 closes the loop. |
| **5. MCP Security Standard** | Gateway with signed manifests, deny-unknown-servers, tool permission model | Q3–Q4 2026 | Ecosystem lock-in. If AMI defines MCP security, every deployment needs AMI. |

### 4.2 Immediate Action Items (Next 10 Weeks)

1. **Engage EU AI Act certification body** — regulatory survival depends on it.
2. **Build hash-chain audit trail** — immutable, append-only, exportable to SIEM.
3. **Implement tool-call interception** — schema validation, permission check, taint propagation, fail-closed.
4. **Implement stop button + action reversal** — legally mandatory per Art. 14(4)(d)(e).
5. **Build Semantic Visor MVP** — Guest/Visor split with STI protocol at every action boundary.
6. **Complete EU AI Act compliance documentation** — classification, risk management, technical docs, deployer toolkit.
7. **Implement gVisor sandbox + MCP gateway** — code execution isolation and MCP ecosystem security.
8. **Begin ISO 27001 evidence pipeline** — certification evidence requires months of collection.

### 4.3 Positioning Statement

> **AMI-Agents is the open-source, sovereign, certifiable security layer for enterprise AI agents.**
>
> Unlike FAANG vendors that lock into one ecosystem, startups that cover fragments, or neoclouds that provide raw compute, AMI provides the complete agent trust plane: fail-closed policy enforcement, hash-chained audit trails, semantic virtualization against prompt injection, sandboxed code execution, multi-agent security, and EU AI Act compliance — deployable on any infrastructure, with any LLM, in any jurisdiction.

---

## 5. Risk Summary ([full register](WS-7-SYNTHESIS-AND-STRATEGY.md#7-3-strategic-risk-register))

| Risk | Likelihood | Impact | Mitigation |
|------|:----------:|:------:|------------|
| EU AI Act compliance deadline missed | Medium | Critical | 4 parallel tracks; cert body engagement week 1; 10-week sprint |
| Prompt injection defence fails under adaptive attack | High | High | Semantic Visor structural prevention; continuous red-teaming |
| ISO 27001/SOC 2 timeline slips 6+ months | Medium | High | Early cert body engagement; dedicated compliance engineer; automated evidence pipeline |
| Multi-agent security not ready before enterprise adoption | Medium | High | Build A2A with security baked in, ship Q4 2026 before mainstream adoption |
| Regulatory fragmentation (EU vs UK vs US) | High | Medium | Modular compliance framework; design for multi-jurisdiction from start |
| VC-funded competitor emerges with agent security focus | High | Medium | Open-source moat; first-mover advantage; certifications; MCP ecosystem |

---

## 6. 18-Month Roadmap ([full detail](WS-7-SYNTHESIS-AND-STRATEGY.md#section-6-18-month-roadmap-q3-2026-q3-2027))

| Quarter | Theme | Key Deliverables | Cumulative Cost |
|---------|-------|-----------------|:---------------:|
| **Q3 2026** | Compliance Foundation | EU AI Act compliance; hash-chain audit; stop button; tool-call interception; gVisor sandbox; Semantic Visor MVP; MCP security gateway; classification docs | €43K |
| **Q4 2026** | Observability + Multi-Agent | OTEL instrumentation; SIEM exporters; A2A protocol (secured); multi-agent orchestration; LLM-in-loop validators; SOC 2 Type I | €110K |
| **Q1 2027** | Memory + Confidential Computing | Behaviour drift detection; cryptographic memory; hierarchical memory (AgentSafe); Confidential Computing (Kata + TDX + CC); 4 security loadout profiles; **ISO 27001 certification** | €168K |
| **Q2 2027** | Formal Verification + Advanced Multi-Agent | Formal DSL runtime verification; G-Safeguard delegation monitoring; neocloud deployment (CoreWeave, Modal, Scaleway); agent evaluation harness; MCP open-source library | €226K |
| **Q3 2027** | Production Maturity + Certification | AgentCrypt FHE; harmonised standards alignment; AMI security benchmark; **SOC 2 Type II**; **ISO 42001 certification** | €273K |

**Total estimated cost**: €273K (4 engineers, 114 engineer-weeks over 18 months).

---

## 7. Closing Assessment ([full synthesis](WS-7-SYNTHESIS-AND-STRATEGY.md#7-8-closing-statement))

Three structural realities define the opportunity:

1. **Containment over prevention.** Prompt injection is structurally inescapable. Semantic virtualization — treating the LLM as an untrusted Guest — is the only viable architectural strategy. The research consensus is clear, but no production implementation exists.

2. **Certifications over features.** ISO 27001 opens more enterprise doors than any feature. SOC 2 keeps them open. ISO 42001 closes the loop. In enterprise procurement, compliance evidence is table stakes. AMI holds zero certifications today.

3. **Multi-agent security built-in, not bolted-on.** The multi-agent attack surface (circular delegation, privilege escalation via orchestration, cross-agent prompt injection) is barely studied. Building A2A with security baked in from day one is the difference between a competitive advantage and a remediation nightmare.

The AMI codebase has the right architectural foundation — the hooks pipeline, command-tier policy engine, and local-first sovereignty posture are strategically correct. The gap between architectural vision and production reality is 12–18 months of focused execution. The EU AI Act deadline in 10 weeks is the forcing function.

**The next 18 months will determine whether AMI-Agents is an enterprise-grade agent security platform or a promising research project.**

---

*This executive summary synthesises findings from seven research workstreams: [WS-1](WS-1-FAANG-GUARDRAILS.md) (FAANG Guardrails), [WS-2](WS-2-SME-ECOSYSTEM.md) (SME/Startup Ecosystem), [WS-3](WS-3-NEOCLOUD-LANDSCAPE.md) (Neocloud Landscape), [WS-4](WS-4-REGULATORY-DEEP-DIVE.md) (Regulatory Deep Dive), [WS-5](WS-5-ACADEMIC-LANDSCAPE.md) (Academic Landscape — 84 papers), [WS-6](WS-6-INCIDENTS-AND-MILESTONES.md) (Incidents & Milestones — 25+ incidents), and [WS-7](WS-7-SYNTHESIS-AND-STRATEGY.md) (Synthesis & Strategy). Full workstream documents located in [`docs/research/`](./).*
