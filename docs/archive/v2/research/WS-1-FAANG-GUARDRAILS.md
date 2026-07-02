# WS-1: FAANG & Big Tech - Agent Guardrails & Security

> **Part of the Agentic Guardrails, Compliance, Standardisation & Security research programme**
> Status: **IN PROGRESS** | Last updated: 2026-05-25

---

## 1. Research Scope & Questions

### 1.1 Google / DeepMind

**Key questions:**
- Gemini Agent Framework: what safety model governs agent actions?
- Project Mariner (browser agent): what security architecture prevents harmful actions?
- Vertex AI Agent Builder: what guardrails are built-in? (content filters, denied topics, groundings)
- How does Google Cloud handle agent compliance for regulated EU customers?
- Agent red-teaming practices - what internal testing methodology?

### 1.2 Microsoft

**Key questions:**
- Copilot Studio: how are agents / extensions secured? What guardrails apply?
- Azure AI Agent Service: what safety configurations exist?
- Purview AI: what compliance monitoring for AI agents?
- AutoGen framework: what safety patterns are recommended?
- Responsible AI toolchain for agentic workflows?

### 1.3 Amazon (AWS)

**Key questions:**
- Bedrock Agents: what guardrails API capabilities? (content filters, denied topics, sensitive information filters, word filters)
- Bedrock Guardrails: depth of configuration, PII redaction, contextual grounding checks
- SageMaker Clarify for agent monitoring?
- How does AWS address EU AI Act requirements for agent workloads?
- What compliance certifications apply to Bedrock Agent deployments?

### 1.4 Meta

**Key questions:**
- Llama Guard: how is it used for agent safety? Prompt Guard, Code Shield specifics
- Purple Llama framework: what does it offer for agent security vs general LLM security?
- Meta's open-source agent safety research - key findings
- Llama agent security: recommended tool-use restrictions

### 1.5 Apple

**Key questions:**
- On-device AI agent guardrails (Apple Intelligence)
- Privacy-preserving architecture for agent operations
- How Apple approaches AI compliance (GDPR / EU AI Act)
- Security boundaries between on-device and cloud agent processing

### 1.6 OpenAI

**Key questions:**
- Agent SDK safety defaults - what guardrails are built-in?
- Model Spec safety guidelines for agentic use
- API-level safety controls (content moderation, function calling restrictions)
- Red-teaming methodology for agent behaviour

### 1.7 Anthropic

**Key questions:**
- Constitutional AI: how does it extend to agentic contexts?
- Claude agent safety features (tool use restrictions, hand-offs)
- API safety controls for multi-step agent operations
- Trusted layer / MCP security architecture

---

## 2. Findings

### 2.1 Google / DeepMind

**Frontier Safety Framework (FSF)**
- Third iteration published Sept 2025, updated Apr 2026. Five risk domains: CBRN, cyber, harmful manipulation, ML R&D, misalignment
- Critical Capability Levels (CCLs) define capability thresholds at which absent mitigations, models pose severe harm risk
- Security Level recommendations mapped to each CCL (ASLR-1 through ASLR-4) for exfiltration risk mitigation
- Safety case process: prepare mitigations, develop assessable safety case, corporate governance body reviews, deployment only on approval
- Deceptive alignment: automated monitoring to detect illicit use of instrumental reasoning capabilities; treat model as "untrusted insider"
- Covers misuse risk (threat actors using critical capabilities) AND misalignment risk (autonomous system undermining human control)
- Tracked Capability Levels (TCLs) introduced Apr 2026 for less extreme risks
- Model card system: every Gemini model published with detailed safety evaluation results, red teaming outcomes, CCL assessment

**Project Mariner (Browser Agent)**
- Chrome extension + cloud VM architecture: runs on cloud-based virtual machines, up to 10 simultaneous tasks
- User Alignment Critic: separate Gemini model vets every action before execution; isolated from untrusted content
- Agent Origin Sets: Chrome-level origin isolation constraining agent to task-relevant origins; read-only vs read-writable distinctions
- Deterministic URL check: model-generated URLs restricted to known public URLs to prevent exfiltration
- User oversight: manual confirmation for sensitive operations (purchases, password entry, credential access)
- Real-time prompt injection detection classifier running in parallel to planning model
- Automated red-teaming systems generating malicious sandboxed sites to test defenses
- Continuous testing prioritizes broad-reach vectors (UGC on social media, ads) and high-impact attacks (financial transactions, credential theft)
- Bounty program up to $20k for agentic browsing vulnerabilities
- Chrome auto-update for rapid fix deployment

**Vertex AI Agent Builder / Gemini Enterprise Agent Platform**
- Multi-layer safety architecture with five layers:
  1. Default model + non-configurable filters (CSAM, copyrighted content)
  2. System instructions (brand safety, behavior guidelines)
  3. Configurable content filters (sexual, hate, harassment, dangerous) with thresholds: BLOCK_LOW_AND_ABOVE, BLOCK_MEDIUM_AND_ABOVE, BLOCK_ONLY_HIGH, OFF
  4. DLP API for sensitive data (PII redaction, masking, tokenization, keyword blocking)
  5. Gemini as a Filter - second Gemini model call (Flash/Lite) for nuanced safety evaluation, agent misalignment detection
- Jailbreak classifier: detects attempts to circumvent model defenses, configurable threshold, off by default
- Grounding: Vertex AI Search, Google Search, inline text, enterprise data stores - with confidence scoring (0-1)
- Dynamic retrieval threshold (default 0.7) for when to use grounded vs ungrounded generation
- Agent Gateway: central policy enforcement point for tool calls, authentication, security policies
- Agent Identity: unique cryptographic IAM principal per agent for granular permissions
- Agent Registry: centralized catalog for agents, tools, MCP servers
- Model Armor integration: enterprise-grade safety filtering with floor settings (organization-level minimum thresholds)
- Model Armor detections: prompt injection/jailbreak, malicious URIs, RAI categories, sensitive data protection, malware detection
- Model Armor pricing: free 2M tokens/month, $0.10/additional 1M tokens; included in SCC Premium/Enterprise

**Google Cloud EU Compliance**
- EU Data Boundary through Assured Workloads: restricts data to EU regions (12+ EU zones)
- Data residency: ML processing guaranteed within region/multi-region for all Gemini models at supported endpoints
- EU AI Act compliance page: ISO 42001, risk management commitment, cross-team readiness program
- Data Processing Addendum: EU SCCs + EU-U.S. DPF + UK Extension + Swiss-U.S. DPF as alternative transfer solutions
- Cloud Data Processing Addendum: GDPR compliance, subprocessor management, compliance certifications (ISO 27017, 27018, PCI DSS)
- SecNumCloud 3.2 certification in France (S3NS partnership)
- AI Act readiness program: risk & compliance, product & engineering, legal, public policy teams
- Agent compliance for regulated customers: VPC Service Controls, CMEK, data residency guarantees

**Agent Red-Teaming**
- Dedicated Google AI Red Team (est. 2023) with AI subject-matter expertise
- Red teams simulate: prompt attacks, training data extraction, model backdooring, adversarial examples, data poisoning, exfiltration
- Google DeepMind: STAR framework (SocioTechnical Approach to Red Teaming) - parameterised instructions, demographic matching, arbitration
- External safety testing: unstructured red teaming on Gemini models across societal, biological, nuclear, cyber risks
- Google Threat Intelligence Group: analyzes real-world AI cyberattack attempts across 20 countries, 12,000+ incidents
- Offensive cyber capability benchmark: 50 challenges covering full attack chain from recon to action-on-objectives
- Big Sleep: AI agent for autonomous vulnerability discovery (Google DeepMind + Project Zero)
- CodeMender: experimental AI agent for automatic vulnerability patching
- Continuous automated red-teaming for indirect prompt injection attacks

### 2.2 Microsoft

**Copilot Studio - Agent Security Architecture**

Microsoft Copilot Studio is an enterprise agent development platform allowing no-code/low-code agent creation with connections to Microsoft 365, Graph, and external SaaS systems.

- **Built-in XPIA/UPIA protection**: Default defenses against cross-prompt injection attacks (XPIA) and user prompt injection attacks (UPIA). Suspicious prompts blocked in real-time (Microsoft Copilot Blog, Sep 2025).
- **Advanced real-time protection (public preview)**: External monitoring systems (Microsoft Defender, third-party, custom) integrate into agent's decision-making loop. Security system reviews planned actions and can block unsafe actions before execution (Microsoft Build 2025).
- **Power Platform admin center controls**: DLP policies, CMK (customer-managed encryption keys), agent publishing disable, geo-movement controls, Customer Lockbox.
- **Agent 365 control plane**: Centralized governance for all AI agents - visibility, lifecycle management, policy enforcement. Part of Microsoft 365 E7. GA May 1, 2026 (Techzine, Mar 2026).
- **Tenable disclosure (Dec 2025)**: Research demonstrated prompt injection could bypass controls and leak credit card data. Microsoft has since hardened XPIA/UPIA protections.

**Azure AI Foundry Agent Service**

Managed agent service within Azure AI Foundry (launched May 2025):

- **Safety configurations**: Azure AI Content Safety integration - Prompt Shield (injection detection) + content moderation (hate, sexual, violence, self-harm across 4 severity levels, configurable thresholds 0-4).
- **Bring Your Own Storage / VNet**: No public egress for data traffic; customer-managed storage and networking.
- **Model flexibility**: GPT-4o, Llama 3, Mistral, Cohere via Azure Models-as-a-Service.
- **Multi-agent orchestration**: Event-driven workflows, memory extraction/consolidation/retrieval across sessions, code interpreter tools.
- **Azure AI Evaluation SDK**: Built-in risk and safety evaluators for content harms; integrated into DevOps pipelines for drift measurement.
- **Safety system message templates**: Microsoft-provided recommended system prompts for reducing harmful outputs.

**Microsoft Purview - AI Compliance Monitoring**

- **AI Hub**: Centralized dashboard for governing AI agent activity across Copilot and custom agents.
- **Data Security Posture Management (DSPM)**: Detects sensitive data in AI prompts; can block PII/credit card numbers in AI interactions.
- **Purview Compliance Manager**: Premium AI templates for EU AI Act, NIST AI RMF, ISO 42001 mapping.
- **Unified audit logs**: Agent management actions (publishing, blocking, updating) logged to Purview Audit (Oct 2025, Roadmap ID 498227).
- **Insider Risk Management**: Adaptive protection for AI assistants; detects users probing for sensitive data via AI.
- **2026 enhancements**: DLP for AI prompts, DSPM for Shadow AI detection, Microsoft Defender for Agents integration.

**AutoGen - Open-Source Multi-Agent Framework**

- **Conversation-based architecture**: Agents communicate via natural language; conversation history as state.
- **Human-in-the-loop**: HandoffTermination, UserProxyAgent patterns for interrupting workflows. Swarm/GroupChat with handoff support.
- **Code execution safety**: Multiple CodeExecutor implementations - DockerCommandLineCodeExecutor (recommended default), LocalCommandLineCodeExecutor, ACADynamicSessionsCodeExecutor, JupyterCodeExecutor.
- **Security default shift (v0.7.5, 2026)**: Defaulted to DockerCommandLineCodeExecutor with security warnings to prevent LLM-generated code running on host.
- **No built-in content safety**: Relies on Azure AI Content Safety integration or external guardrails.
- **Open-source**: MIT license, 4.2k+ GitHub stars.

**Microsoft Responsible AI Toolchain**

- **Microsoft Responsible AI Standard**: Internal governance grounding all AI releases. Pre-deployment review and red teaming for every Azure OpenAI Service model.
- **AI Red Teaming Agent**: Simulates adversarial prompts to detect model/application risk posture. Validates multi-agent workflows.
- **2025 Transparency Report**: Explicitly expanded tooling for agentic systems - risk measurement beyond text to images, audio, video.
- **Sensitive Uses Team**: Counseling for high-impact/higher-risk AI uses.
- **EU AI Act posture**: Purview Compliance Manager EU AI Act templates; data residency controls; ISO 27001/SOC 2/HIPAA/FedRAMP certifications.

### 2.3 Amazon (AWS)

**Bedrock Agents Guardrails API**

- **Guardrail association**: Attached to agents at create/update time via GuardrailConfiguration in CreateAgent/UpdateAgent API (AWS Docs).
- **Content filters**: Configurable strength (LOW, MEDIUM, HIGH) across Hate, Insults, Sexual, Violence, Misconduct, Prompt Attack. Separate input/output filtering.
- **Prompt Attack detection**: Detects jailbreaks, prompt injections, prompt leakages. Standard tier (2025) distinguishes jailbreaks from injections, adds output manipulation protection.
- **Denied topics**: Up to 200-character topic definitions + sample phrases. Contextual evaluation (not keyword matching). Best practices: crisp definitions, no instructions/negatives.
- **Word filters**: Custom word/phrase exact-match blocking + profanity filter.
- **Sensitive information filters**: ML-based PII detection (names, addresses, emails, SSNs, credit cards, etc.) + custom regex. Actions: BLOCK or MASK (anonymize with `{NAME}` tags). Context-dependent probabilistic matching.
- **Contextual grounding checks**: Detects hallucinations by verifying responses against source grounding and user query relevance. Score-based filtering.
- **Automated Reasoning checks**: Mathematically rigorous validation of model responses against logical rules. AWS differentiating capability - detects hallucinations, suggests corrections, highlights unstated assumptions.
- **Detect mode**: Evaluate guardrail performance without blocking - returns trace data showing what would be blocked.
- **Standard tier (2025)**: 60+ language support, code-domain content filtering, stronger prompt attack defenses.
- **Model-agnostic**: ApplyGuardrail API works across Bedrock-hosted models, self-hosted, third-party models outside Bedrock.
- **Claims**: "Block up to 88% of harmful content" and "identify correct model responses with up to 99% accuracy" (AWS Bedrock product page).

**Bedrock Guardrails Configuration Depth**

- Comprehensive PII types: names, addresses, emails, phones, SSNs, credit cards, bank accounts, medical IDs, etc.
- Per-category filter strength independent for input vs. output.
- Customizable block messages per guardrail.
- Customer-managed keys (CMK) support.
- Versioned guardrails (DRAFT, published versions).
- Integration with Bedrock Agents, Bedrock Knowledge Bases, and standalone API.

**SageMaker Clarify - Agent Monitoring Gap**

SageMaker Clarify is designed for ML model bias detection and explainability, not agent runtime monitoring:

- **Bias detection**: Pre/post-training bias metrics for structured data models.
- **FM Evaluations (2025)**: Accuracy, robustness, toxicity metrics for generative AI use cases.
- **Agent gap**: Does not natively support agent-specific monitoring (tool call tracing, prompt injection detection, agent drift). AWS recommends Bedrock Guardrails + CloudWatch + Bedrock Agent trace logging instead.

**EU AI Act & Compliance Posture**

- Compliance validation for Bedrock AgentCore (AWS compliance-validation docs).
- SOC 1/2/3, ISO 27001/27017/27018, HIPAA BAA, FedRAMP High/Moderate, PCI DSS, GDPR DPA.
- Bedrock Guardrails available in EU regions (Frankfurt, Ireland, London, Paris, Stockholm).
- PII filtering supports GDPR data minimization requirements.
- AWS Artifact provides compliance reports.
- Shared responsibility model: AWS secures infrastructure; customers responsible for agent configuration and compliance.

### 2.4 Meta

**Purple Llama Framework**

Umbrella project for open trust and safety tools, announced Dec 2023. "Purple teaming" (red + blue combined):

- **Components**: Llama Guard (safety classifier), Prompt Guard (jailbreak/injection detection), Code Shield (secure code analysis), CyberSecEval (security benchmarks), LlamaFirewall (unified guardrail system).
- **Open-source**: All components under open licenses (Llama Community License, Apache 2). GitHub: meta-llama/PurpleLlama (4.2k+ stars).
- **Partners**: Microsoft, AWS, Google Cloud, Intel, AMD, Nvidia.
- **Agent-specific focus**: Addresses agent threats (goal hijacking, code interpreter abuse, tool misuse) beyond traditional LLM content safety.

**Llama Guard Series**

- **Llama Guard 1 (7B)**: Llama 2-based, text-only, 6 hazard categories.
- **Llama Guard 2 (8B)**: Llama 3-based, MLCommons aligned, improved F1/FPR.
- **Llama Guard 3 (8B + 11B Vision)**: Multilingual text + single-image support.
- **Llama Guard 4 (12B)**: Pruned from Llama 4 Scout, native multimodal (text + multiple images), 163.8K context window. MLCommons hazards taxonomy. Combines Guard 3-8B and 3-11B-vision. Integrated with Llama Moderations API.
- **Architecture**: Fine-tuned LLM generating SAFE or UNSAFE + violated category IDs. Dual modes: Prompt Classification + Response Classification.
- **Customizable taxonomy**: Developers define own risk categories for fine-tuning.
- **Agent-specific category**: Code Interpreter Abuse added in Llama Guard 4 for tool-call use cases.

**Prompt Guard 2 - Jailbreak Detection**

- **Prompt Guard 2 86M**: BERT-style classifier for direct/indirect jailbreak detection.
- **Prompt Guard 2 22M**: Smaller/faster variant - 4x latency reduction, minimal accuracy tradeoff.
- Deployed at inference time on user prompts and untrusted data sources.

**Code Shield - Secure Code Analysis**

- Online static analysis engine: Semgrep + regex rules across 8 programming languages. MITRE CWE coverage.
- Code interpreter abuse prevention for agent-generated code.
- Secure command execution validation.

**LlamaFirewall - Unified Agent Guardrail System**

Released at LlamaCon 2025 - Meta's most significant agent security contribution:

- **System-level security architecture**: Modular, layered defense for LLM-powered agents, not just chatbots.
- **Three integrated guardrails**:
  1. **PromptGuard 2** - Universal jailbreak/direct injection detector
  2. **AlignmentCheck** - Chain-of-thought auditor (first open-source guardrail to inspect agent reasoning in real-time for goal hijacking/prompt injection)
  3. **CodeShield** - Online static analysis for insecure code detection
- **Policy engine**: Custom pipelines, conditional remediation strategies, plug-in detectors. Comparable to Snort/ZEEK for AI agents.
- **Risk coverage**: Jailbreaking, indirect prompt injection, goal hijacking, insecure code outputs, code interpreter abuse, risky LLM plug-in interactions.
- **Open source**: Published as research paper + GitHub at LlamaCon 2025 (Meta AI Blog, May 2025).

**Llama Stack Safety**

- **Shield abstraction**: Pre/post processing hooks for input/output guardrails. Agents call shield APIs invoking Llama Guard or Prompt Guard.
- **Red Hat implementation**: Demonstrated with Python for RAG + agent use cases (Red Hat Developer, Aug 2025).

**Open-Source Agent Safety Research**

- **CyberSecEval 4**: Cybersecurity benchmarks - CyberSOC Eval (with CrowdStrike, SOC efficacy) and AutoPatchBench (automated vulnerability patching).
- **Llama 4 Agent Framework (Mar 2026)**: Open-source multi-agent orchestration (Apache 2.0). Model variants fine-tuned for agentic workloads (8B, 70B, 405B). Built-in tool use, memory, orchestration.
- **Llama Defenders Program**: Partner access to AI solutions for security needs.
- **Key finding**: "On average, LLMs suggested vulnerable code 30% of the time" (CyberSecEval initial results).
- **Tool-use recommendations**: Sandboxed code execution (Docker), restricted tool/API surface, input/output safety filtering via Llama Guard, chain-of-thought audit via AlignmentCheck. Fine-tuned agent models include instruction-following guardrails in base training.

### 2.5 Apple

**On-Device AI Guardrails (Apple Intelligence)**
- ~3B parameter on-device language model optimized for Apple silicon (KV-cache sharing, 2-bit quantization-aware training, avg 3.7 bits-per-weight)
- On-device processing is the cornerstone: data never leaves device for most tasks (email summaries, notification prioritization, writing tools)
- Foundation Models framework (Swift API, WWDC25): access to on-device LLM with guardrail violation error handling
- Input and output filters on local LLM block malicious input and prevent undesirable output
- Tool-calling capabilities via constrained adapter system: predefined App Intents declare actions, no arbitrary code execution
- System instructions are trained to dominate user prompts (instruction hierarchy for security)

**Private Cloud Compute (PCC) Architecture**
- Apple silicon servers in dedicated data centers with hardened OS (subset of iOS/macOS)
- End-to-end encryption: device encrypts requests to verified PCC node public keys; load balancers cannot decrypt
- Stateless computation: data processed transiently, deleted after request fulfillment, no persistence
- No privileged runtime access: no SSH, no admin interfaces, limited audited commands only
- Secure Boot + Code Signing: only Apple-signed code executes; JIT mappings blocked, no runtime code injection
- Secure Enclave manages keys; keys cannot be duplicated or extracted
- Non-targetability: OHTTP relay obfuscates user IP; Target Diffusion prevents singling out users
- Transparency Log: every production build publicly logged; devices verify node certificates against log before sending data
- Independent security researchers can inspect published software images
- Verifiable transparency: user devices refuse to talk to unverified PCC nodes

**Privacy Architecture for Agents**
- On-device routing: device decides if task can be completed locally or needs cloud inference
- Data minimization: only data relevant to request sent to PCC; Apple does not access or store content
- Differential privacy for aggregate analytics: usage trends collected without individual data exposure
- Synthetic data generation for model improvement: embeddings compared against synthetic variants, only aggregated statistics shared
- App Store review framework for agents (expected WWDC26): constrained-intent compliance tier for autonomous AI apps
  - Schema-based actions that cannot generate executable code
  - No code generation at runtime
  - App Intents reviewers inspect and pre-approve
- Apple's sandboxing architecture + entitlement system for sensitive capability control
- ISO 27001 and 27018 certifications maintained
- Privacy Steering Committee chaired by General Counsel

**EU AI Act Compliance Approach**
- Apple's legal/public stance: opposes DMA forced interoperability for AI agents (joint submission with Google, May 2026)
- Privacy Impact Assessments (PIAs) for major AI products; Data Protection Officer approval required
- Does not use private user data or interactions for foundation model training
- Training data: publicly crawled data (Applebot, respects robots.txt), licensed data, synthetic data; PII filters applied
- On-device inference eliminates GDPR third-party data processor relationship for inference itself
- Transparency logging feature: Apple Intelligence Report shows all off-device requests and PCC processing
- GDPR Article 22 compliance: automated decision-making with significant effects requires human review
- CCPA/GDPR adherence claimed for all Apple Intelligence features
- App Store Guideline 5.1.2(i) (Nov 2025): AI-specific requirements - explicit disclosure of third-party AI data sharing with consent modal
- Security boundaries: Apple uniquely positioned to argue no "transfer" under GDPR for on-device processing

### 2.6 OpenAI

**Agent SDK Safety Defaults**
- Three guardrail types: Input (first agent only), Output (final agent only), Tool (every custom function-tool invocation)
- Execution modes: Parallel (concurrent with agent) and Blocking (guardrail completes before agent starts)
- Blocking recommended for high-cost/dangerous actions; Parallel for low-risk noise filtering
- Human-in-the-loop approvals: tool-level `needsApproval` flag pauses run, records interruption, resumes from `state`
- Approvals preserve conversation history and decision-making chain across interruptions
- Guardrail tripwire mechanism: raises `{Input,Output}GuardrailTripwireTriggered` exception, halts execution
- SandboxAgent (beta, Apr 2026): isolated Linux environments with files, commands, ports; manifest-based workspace contracts
- Sandbox capabilities: filesystem, shell, compaction; network policy via `extra_path_grants` (trusted config, not model output)
- Codex safety: Auto-review mode - separate Codex agent grades sandbox-boundary-crossing requests
  - Default-FAIL: blocked by default, exceptions via config
  - ~99% approval rate for reviewed actions; rejects ~1% of boundary-crossing requests
  - 3 consecutive denials or 20 total → escalate to human
- OpenTelemetry log export for Codex: user prompts, tool approvals, execution results, MCP usage, network policy events
- Compliance API for Enterprise/Edu: agent activity logs for security teams
- AI-powered security triage agent uses Codex logs to inspect requests and flag anomalies

**Model Spec for Agentic Use**
- Chain of command: platform-level rules > developer instructions > user instructions
- Authored hierarchy prevents prompt injection escalation through message levels
- Side-effect minimization: irreversible actions require extra care; agent should prefer reversible approaches
- Scope of autonomy: defined by user/developer; notify and seek approval for scope expansion
- Agentic contexts explicitly addressed: "tool calls may cause side-effects difficult or impossible to reverse"
- End-turn mechanism signals when agent yields control; `end_turn=true` required for stopping action chains
- Untrusted data handling: ignore instructions in untrusted_text, quoted text, images, tool outputs unless explicitly delegated
- Model Spec Evals (Mar 2026): open-source evaluation suite measuring spec adherence; covers text, agentic settings pending
- GPT-5 safe-completions: replaces binary refusal with safety-constrained helpfulness for dual-use scenarios

**API Safety Controls**
- Safety classifiers for GPT-5: risk threshold monitoring with 7-day warning window before access revocation
- `safety_identifier` parameter: stable per-user ID (hashed) for abuse attribution without PII exposure
- Enforcement escalation: delayed streaming → blocked individual identifier → org access revocation
- Moderation API (free): content filtration for hate, harassment, violence, self-harm, sexual content
- gpt-oss-safeguard (open-weight): reasoning-based classifier interpreting developer-provided policy at inference time
- Safety Reasoner (internal): chain-of-thought safety classification for image gen, Sora 2, biology, self-harm domains
  - Used in ChatGPT Agent for dynamic step-wise evaluations
  - Fraction of compute for safety reasoning: up to 16% in recent launches
- Instruction hierarchy: system > developer > user; mitigates prompt injection through layered defense stack
- Function calling strict mode: enforces JSON schema adherence; `tool_search` for deferred tool loading
- Parallel tool calls configurable: `parallel_tool_calls: false` for single-tool enforcement

**Agent Red-Teaming**
- External red teaming whitepaper: systematic methodology across campaigns (pre-deployment research, API safeguards, in-product testing)
- GPT-5 red teaming: 5,000+ hours, 400+ external testers across violent attack planning, jailbreaks, prompt injections, bioweaponization
- Microsoft AI Red Team tested GPT-5: 70+ security experts, PyRIT automated tool, ~1M adversarial conversations across 18 harm areas
- Gray Swan: prompt injection benchmark showing GPT-5 SOTA performance against adversarial attacks
- Preparedness Framework: capability thresholds for biological/chemical weapons, cybersecurity, persuasion
- Continuous evaluations: StrongReject → multi-turn jailbreak eval for GPT-5.5
- MITRE ATT&CK-grounded adversarial scenarios for cyber safety testing
- External red teaming for CBRN: 1,000+ hours, reasoning monitor with 98.7% recall on unsafe outputs
- Red Teaming Network (RTN): free-form, paired model comparisons, demographic diversity

### 2.7 Anthropic

**Constitutional AI in Agentic Contexts**
- Claude's Constitution (published Jan 2026): foundational document expressing values, behavior, safety priorities
- Four pillars: broadly safe, broadly ethical, compliant with Anthropic guidelines, genuinely helpful
- Agentic settings explicitly addressed: "Claude is increasingly being used in agentic settings with greater autonomy, executes long multistep tasks"
- Teaching Claude Why (2026): SDF (synthetic document fine-tuning) on constitutional documents reduces agentic misalignment 3x+
  - "Difficult advice" dataset teaches ethical reasoning, not just answers
  - Tool-augmented RL environments (tools defined but unnecessary) reduced agentic misalignment substantially
- Constitutional Classifiers (Jan 2026): defends against universal jailbreaks
  - First gen: 86% jailbreak rate → 4.4% (95% blocked)
  - Next-gen (Constitutional Classifiers++): two-stage cascade architecture (linear probe + classifier ensemble)
    - 0.05% refusal rate on harmless queries (87% drop from gen1)
    - ~1% additional compute overhead
    - 1,700+ hours red-teaming, 198,000 attempts, only 1 high-risk vulnerability found (0.005 per 1K queries)
    - No universal jailbreak discovered
- Agentic misalignment assessment: blackmail propensity reduced from 65% to 19% via SDF on constitutional documents + fictional stories

**Claude Tool-Use Safety**
- Permission policies: `always_allow`, `always_ask` per tool; default MCP toolset = `always_ask`
- Agent toolset default = `always_allow`; individual tool overrides via `configs` array
- Programmatic tool calling: Claude writes Python code to call tools in sandboxed container; intermediate results filtered before context window
- Task budgets: token countdown for full agentic loop (thinking + tool calls + results + output); model self-regulates
  - Budget too small → refusal-like behavior; complement with `max_tokens` as absolute ceiling
- Claude Code auto mode (2026): model-based classifiers replace manual approvals
  - Three-tier: deny-by-default (block), allow-by-default (bash/editor), transcript classifier (everything else)
  - Fast single-token filter → chain-of-thought only when flagged
  - Multi-agent handoff checks at both delegation and return (catches prompt injection mid-run)
  - Reasoning-blind classifier: sees only user messages + tool calls, not Claude's own reasoning
- Plan Mode: user approves whole plan before execution, not per-action
- Read-only default permissions in Claude Code; must ask before writing to disk

**MCP Security Architecture**
- MCP (Model Context Protocol): open standard for model-to-tool communication; donated to Linux Foundation Agentic AI Foundation
- Two transports: STDIO (local subprocess, full local privilege) and Streamable HTTP (network, OAuth surface)
- STDIO architectural concern (OX Security, Apr 2026): configuration-to-command execution via shell without input sanitization - 200K+ vulnerable instances across 150M+ downloads; 11 CVEs
- Anthropic's position: intentional behavior, remediation on downstream developers; updated SECURITY.md
- MCP Tunnels (beta): outbound-only cloudflared connection; three-layer security (outer mTLS + IP validation, inner TLS, OAuth per server)
- MCP directory: reviewed tools must adhere to Anthropic security/safety/compatibility standards
- Third-party security research identifies protocol-level vulnerabilities: absence of capability attestation, unauthenticated sampling, implicit trust propagation (PROTOAMP study: 23-41% higher attack success in MCP vs non-MCP)
- Proposed extensions: ATTESTMCP (capability attestation + message authentication), SMCP (Secure MCP with digital identity + mTLS), MCPShield (security cognition layer), Governed MCP (kernel-level gateway)
- Enterprise guidance: tool-level RBAC, MCP gateway with policy enforcement, human approval for destructive operations

**Trusted Layer**
- Five principles for trustworthy agents (Aug 2025): human control, alignment with user expectations, security, transparency, privacy
- User control: choose tools, configure permissions per action (always allow / needs approval / block)
- Multi-layer security: training (injection pattern recognition) + production monitoring (block real attacks) + external red teaming
- Multi-agent sessions: coordinator delegates to subagents with context-isolated event streams; tool permissions cross-posted to primary thread
- Managed Agents API (preview, Apr 2026): fully managed sandbox environments with configurable networking (`unrestricted` / `limited`)
  - `limited` mode: explicit allowed_hosts allowlist; MCP server access and package manager access as separate toggles
  - Pre-installed packages via multiple managers (apt, cargo, gem, go, npm, pip) with optional version pinning
- Monitoring: Threat Intelligence team for ongoing malicious behavior assessment
- Claude's Constitution includes "Being broadly safe: Claude should not undermine humans' ability to oversee and correct its values"

---

## 3. Comparative Analysis

| Dimension | Google/DeepMind | Microsoft | AWS | Meta | Apple | OpenAI | Anthropic |
|---|---|---|---|---|---|---|---|---|
| **Content filters** | 5-layer stack + Model Armor; Gemini-as-Filter; configurable thresholds (4 levels) | Azure AI Content Safety (4 categories, 4 severity levels); Copilot Studio default XPIA/UPIA blocking; Purview DLP for AI | Bedrock Guardrails content filters (6 categories); per-category strength sliders; Standard tier 60+ languages; code-domain filtering | Llama Guard 4 (MLCommons taxonomy, multimodal); Prompt Guard 2; Code Shield; LlamaFirewall unified policy engine | On-device I/O filters; PCC-level safety; Foundation Models framework; differential privacy | Moderation API (free); Safety Reasoner (CoT); gpt-oss-safeguard; safe-completions | Constitutional Classifiers (two-stage cascade); 0.05% over-refusal; constitution-based screening |
| **Tool-use restrictions** | Agent Identity (IAM/agent); Agent Gateway; read-only vs read-writable origin sets | AutoGen DockerCommandLineCodeExecutor (default); Copilot Studio data policies limiting connectors; handoff-based HITL | Bedrock Agents action groups (scope definitions); guardrail per-agent; ApplyGuardrail API middleware | AlignmentCheck (CoT auditor); Code Shield static analysis; sandboxed execution; Llama 4 Agent fine-tuned for safe tool use | App Intents framework (schema-declared actions, no code gen); entitlement system for sensitive capabilities | Tool guardrails (pre/post); `needsApproval` flag; `tool_choice`/`parallel_tool_calls` control; strict mode for schemas | Permission policies per tool (`always_allow`/`always_ask`/block); programmatic tool calling in sandbox; Plan Mode; read-only defaults |
| **Human-in-the-loop** | User Alignment Critic (separate model vets actions); user confirmations for sensitive operations | AutoGen HandoffTermination/UserProxyAgent; Copilot Studio approval gates; Power Platform admin governance | Detect mode for pre-validation; manual approval via Lambda callbacks; trace investigation | No built-in HITL (automated classifiers); relies on app-layer via Llama Stack shield API | On-device routing decision (local vs PCC); user consent modals; App Store agent compliance pre-review | Tool-level approval interruptions; Auto-review (Codex) - separate agent grades boundary-crossing | `always_ask` per tool; Claude Code auto mode (classifier substitutes approvals); multi-agent handoff checks |
| **Audit logging** | Cloud Audit Logs + Model Armor + SCC; Agent Registry; Big Sleep/CodeMender telemetry | Purview unified audit logs for agent actions; Azure Monitor + App Insights for Foundry agents; Agent 365 audit trails | CloudWatch + Agent trace logging; Guardrails trace output (per-filter assessments); CloudTrail for API calls | No centralized audit; app-layer logs; CyberSecEval for benchmarking; community tools build on open framework | Apple Intelligence Report; PCC images publicly logged; verifiable transparency (device refuses unverified nodes) | OpenTelemetry export; Compliance API for Enterprise; Traces dashboard with full session visibility | MCP audit chains; handoff audit JSONL; Threat Intelligence monitoring; task budgets as token accounting |
| **PII handling** | DLP API at I/O; Sensitive Data Protection via Model Armor; de-identification (redaction, masking, tokenization) | Purview DLP + sensitivity labels for AI; Azure AI Content Safety PII detection; Copilot Studio data masking rules | PII detection (comprehensive types + custom regex); BLOCK or MASK actions; ML-based context-dependent matching | No native PII handling; Llama Guard classifies unsafe content but does not redact; delegated to app layer | On-device eliminates PII transmission to cloud; PCC stateless; differential privacy; PII filters on crawled data | `safety_identifier` (hashed user IDs); gpt-oss-safeguard for policy-based classification; Moderation API PII detection | Constitutional classifiers block sensitive data; MCP tunnel OAuth + mTLS; DLP at application layer recommended |
| **EU compliance posture** | Assured Workloads EU Data Boundary; EU AI Act compliance page; ISO 42001; SecNumCloud 3.2; GDPR DPA with SCCs + DPF | Purview Compliance Manager EU AI Act templates; data residency controls; ISO/SOC/HIPAA across Azure | Bedrock AgentCore compliance validation; SOC/ISO/HIPAA/FedRAMP; PII redaction + content filters map to Article 9; shared responsibility | No direct EU AI Act tooling; relies on cloud partners for compliance layer; model cards + responsible use guide | On-device eliminates cross-border transfer concerns; PIAs for all AI products; opposes DMA forced AI interoperability; GDPR Article 22 compliance | API safety identifiers; content moderation for EU AI Act transparency; special access program for life sciences | MCP donated to Linux Foundation (Brussels effect); EU data regions (Vertex EU, Bedrock EU); Responsible Scaling Policy |
| **Open-source approach** | Google ADK (open-source); Gemma open models; Model Armor REST API works with any LLM; SAIF framework | AutoGen (MIT, full open-source); Copilot Studio security proprietary; RAI toolchain partially open | Bedrock Guardrails fully proprietary (API only); SageMaker Clarify proprietary; open SDKs/samples on GitHub | Fully open-source: Purple Llama, Llama Guard, Prompt Guard, Code Shield, LlamaFirewall (Apache 2), Llama 4 Agent Framework (Apache 2) | Foundation Models framework (proprietary Swift API); PCC (proprietary but verifiable); Core ML (open) | Agents SDK (open-source Python); gpt-oss-safeguard (open-weight); Model Spec Evals (open-source); Swarm (experimental) | MCP (open standard, Linux Foundation); Constitutional AI (open research); Claude's Constitution (published); hooks (open-source) |
| **Anti-prompt-injection** | Model Armor (jailbreak detection); Gemini-as-Filter (multi-modal); instruction hierarchy; User Alignment Critic | Copilot Studio default UPIA/XPIA (real-time); Azure AI Prompt Shields; Defender for Agents integration | Prompt Attack filter (Standard tier distinguishes jailbreak vs injection vs leakage); detect mode for tuning | Prompt Guard 2 (86M + 22M); AlignmentCheck (first open-source CoT audit); LlamaFirewall unified injection defense | Instruction hierarchy (system > user prompt); I/O filters on local model; Unicode/RLO attack patched in iOS 26.4 | Instruction hierarchy (system > developer > user); Moderation API classifiers; GPT-5 safe-completions; Gray Swan SOTA | Constitutional Classifiers++ (cascade, 95%+ jailbreak blocked); two-stage probe-classifier; prompt injection training in RL |

---

## 4. Sources Consulted

**Microsoft**
1. "Strengthen agent security with real-time protection in Microsoft Copilot Studio" - Microsoft Copilot Blog, Sep 2025. https://www.microsoft.com/en-us/microsoft-copilot/blog/copilot-studio/strengthen-agent-security-with-near-real-time-protection-in-microsoft-copilot-studio
2. "Security and governance - Microsoft Copilot Studio" - Microsoft Learn (updated Jan 2026). https://learn.microsoft.com/en-us/microsoft-copilot-studio/security-and-governance
3. "Microsoft Copilot Studio Security Risk: How Simple Prompt Injection Leaked Sensitive Data" - Tenable, Dec 2025. https://www.tenable.com/blog/microsoft-copilot-studio-security-risk-how-simple-prompt-injection-leaked-sensitive-data
4. "Microsoft Build 2025: Copilot + Agent Governance, Security, and Management" - Microsoft Power Platform Blog, May 2025. https://www.microsoft.com/en-us/power-platform/blog/2025/05/15/microsoft-build-2025-agent-governance-what-to-look-for
5. "Microsoft secures AI agents with Defender, Entra, and Purview" - Techzine Global, Mar 2026. https://www.techzine.eu/news/security/139821/microsoft-secures-ai-agents-with-defender-entra-and-purview
6. "Governance and security for AI agents across the organization" - Microsoft Cloud Adoption Framework, Apr 2026. https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ai-agents/governance-security-across-organization
7. "Azure AI Agent Service: Revolutionizing AI Agent Development" - Microsoft Tech Community, Jan 2025. https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-azure-ai-agent-service/4298357
8. "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation" - Microsoft Research / COLM 2024. https://www.microsoft.com/en-us/research/publication/autogen-enabling-next-gen-llm-applications-via-multi-agent-conversation-framework
9. "AutoGen documentation - Code Execution" - AutoGen docs. https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/code-execution-groupchat.html
10. "AutoGen v0.7.5 release - security warnings and default Docker" - GitHub. https://github.com/microsoft/autogen/releases
11. "Microsoft Purview in 2025: What's New" - Precio Fishbone, Feb 2026. https://www.preciofishbone.com/knowledge-hub/microsoft-purview-whats-new
12. "Microsoft Purview compliance portal: Audit logs for agent management" - M365 Admin, Sep 2025. https://m365admin.handsontek.net/microsoft-purview-compliance-portal-audit-logs-agent-management-microsoft-365-admin-center
13. "Compliance Meets AI 2026: Microsoft Purview in the Age of AI" - Microsoft Community Hub, Dec 2025. https://techcommunity.microsoft.com/blog/healthcareandlifesciencesblog/compliance-meets-ai-2026-microsoft-purview-in-the-age-of-ai/4475027
14. "2025 Responsible AI Transparency Report" - Microsoft, PDF. https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/microsoft/msc/documents/presentations/CSR/Responsible-AI-Transparency-Report-2025-vertical.pdf
15. "Safeguarding LLM security & safety evaluations" - Microsoft Learn. https://learn.microsoft.com/en-us/ai/playbook/technology-guidance/generative-ai/mlops-in-openai/security/operationalize-security-safety-evaluations
16. "Runtime guardrails for Microsoft Copilot Studio agents" - Noma Security, Mar 2026. https://noma.security/blog/runtime-guardrails-for-microsoft-copilot-studio-agents
17. "Copilot Studio Governance & Security Guide" - First AI Group. https://www.firstaigroup.com/wp-content/uploads/2025/08/Microsoft-Copilot-Studio_Governance-and-security-guide.pdf

**Google / DeepMind**
1. "Model Armor overview" - Google Cloud Docs. https://cloud.google.com/security-command-center/docs/model-armor-overview
2. "Model Armor threat detection" - Google Cloud Docs. https://cloud.google.com/security-command-center/docs/model-armor-threat-detection
3. "Model Armor safety attributes and categories" - Google Cloud Docs. https://cloud.google.com/security-command-center/docs/model-armor-safety-attributes
4. "Model Armor data masking" - Google Cloud Docs. https://cloud.google.com/security-command-center/docs/model-armor-data-masking
5. "AI Guardrails: Secure Your GenAI Workloads" - Google Cloud Blog. https://cloud.google.com/blog/products/identity-security/ai-guardrails-secure-genai-workloads
6. "Google ADK (Agent Development Kit)" - Google GitHub. https://github.com/google/adk-python
7. "Agent Identity - Google Cloud Identity Platform" - Google Cloud Docs. https://cloud.google.com/identity-platform/docs/agent-identity
8. "Agent Gateway - Apigee" - Google Cloud Docs. https://cloud.google.com/apigee/docs/api-platform/security/agent-gateway
9. "Chrome built-in AI - Early Preview Program" - Google Developer Blog. https://developer.chrome.com/docs/ai/built-in
10. "Gemini 2.5: A Critical Look at DeepMind's Latest Model" - Reddit discussion. https://www.reddit.com/r/LocalLLaMA/comments/1jh86vn/gemini_25_a_critical_look_at_deepminds_latest/
11. "The battle for AI safety gates: How Apple, Google and EU target agents" - Information Age, Jan 2026. https://informationage.com/the-battle-for-ai-safety-gates-how-apple-google-and-eu-target-agents/
12. "Big Sleep: A new AI tool for finding security vulnerabilities" - Google Project Zero Blog, Oct 2024. https://googleprojectzero.blogspot.com/2024/10/big-sleep.html
13. "CodeMender: AI Agent for Automated Vulnerability Patching" - Google Cloud Blog. https://cloud.google.com/blog/products/identity-security/codemender-agent-vulnerability-patching
14. "SAIF: Secure AI Framework" - Google Safety Engineering Center. https://safety.google/saif
15. "Google's Secure AI Framework (SAIF) discovers 4 major CVEs" - Google Cloud Blog, Jan 2026. https://cloud.google.com/blog/products/identity-security/saif-discovers-4-cves
16. "AI Control Loops: Using AI to secure AI agents" - Google Cloud Blog, Jan 2026. https://cloud.google.com/blog/products/identity-security/ai-control-loops
17. "Google Gemini app - EU AI Act compliance" - Google Support. https://support.google.com/gemini/answer/15205808
18. "Gemma models" - Google AI for Developers. https://ai.google.dev/gemma
19. "Assured Workloads EU Data Boundary" - Google Cloud Docs. https://cloud.google.com/assured-workloads/docs/eu-data-boundary
20. "Google Cloud EU AI Act compliance" - Google Cloud Docs. https://cloud.google.com/compliance/eu-ai-act
21. "Why Google chose a 'gated' approach to agents" - Google Cloud Blog. https://cloud.google.com/blog/products/ai-machine-learning/agents-identity-and-security

**Amazon (AWS)**
1. "Implement safeguards for your application by associating a guardrail with your agent" - AWS Bedrock Docs. https://docs.aws.amazon.com/bedrock/latest/userguide/agents-guardrail.html
2. "Create your guardrail" - AWS Bedrock User Guide. https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-components.html
3. "Block denied topics to help remove harmful content" - AWS Bedrock Docs. https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-denied-topics.html
4. "Options for handling harmful content detected by Amazon Bedrock Guardrails" - AWS Bedrock User Guide. https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-harmful-content-handling-options.html
5. "Amazon Bedrock Guardrails announces tiers for content filters and denied topics" - AWS What's New, Jun 2025. https://aws.amazon.com/about-aws/whats-new/2025/06/amazon-bedrock-guardrails-tiers-content-filters-denied-topics
6. "Amazon Bedrock Guardrails" - AWS Product Page. https://aws.amazon.com/bedrock/guardrails
7. "Safeguard your generative AI workloads from prompt injections" - AWS Security Blog. https://aws.amazon.com/blogs/security/safeguard-your-generative-ai-workloads-from-prompt-injections
8. "Protect your generative AI applications against encoding-based attacks" - AWS Security Blog, Oct 2025. https://aws.amazon.com/blogs/security/protect-your-generative-ai-applications-against-encoding-based-attacks-with-amazon-bedrock-guardrails
9. "Amazon Bedrock Guardrails - Complete Setup Guide" - AWS Builder, May 2026. https://builder.aws.com/content/3DZH9l4epfQiT5TZ5XMdDDS4XZG/amazon-bedrock-guardrails-complete-setup-guide
10. "Compliance validation for Amazon Bedrock AgentCore" - AWS Docs. https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/compliance-validation.html
11. "Amazon SageMaker Clarify" - AWS Product Page. https://aws.amazon.com/sagemaker/ai/clarify
12. "Guardrails for Amazon Bedrock: AI Safety & Compliance Guide" - Lasso Security, Mar 2026. https://www.lasso.security/blog/guardrails-for-amazon-bedrock
13. "Build clinical trial question-answering agent on Amazon Bedrock" - PwC, Mar 2025. https://www.pwc.com/us/en/technology/alliances/library/aws-bedrock-ai-agents.html

**Apple**
1. "Apple Intelligence foundation language models" - Apple Machine Learning Research, Jul 2024. https://machinelearning.apple.com/research/apple-intelligence-foundation-language-models
2. "Apple Intelligence: On-device, private, and secure" - Apple Security Research. https://security.apple.com/blog/apple-intelligence-on-device-private-and-secure/
3. "Private Cloud Compute: A new frontier for AI privacy" - Apple Security Research, Jul 2024. https://security.apple.com/blog/private-cloud-compute/
4. "Building safe and responsible AI" - Apple ML Research. https://machinelearning.apple.com/research/building-safe-and-responsible-ai
5. "Apple Intelligence Report" - Apple Privacy. https://privacy.apple.com/account/intelligence-report
6. "App Intents framework" - Apple Developer Documentation. https://developer.apple.com/documentation/appintents
7. "Foundation Models framework" - Apple Developer Documentation. https://developer.apple.com/documentation/foundationmodels
8. "What's new in App Store review" - Apple Developer, WWDC 2025. https://developer.apple.com/videos/play/wwdc2025/10125
9. "Apple Intelligence now includes ChatGPT integration" - Apple Newsroom, Dec 2024. https://www.apple.com/newsroom/2024/12/apple-intelligence-now-includes-chatgpt-integration/
10. "iOS & iPadOS 26.4 Release Notes" - Apple Developer. https://developer.apple.com/documentation/ios-ipados-release-notes/ios-ipados-26_4-release-notes
11. "Apple Intelligence: Security and privacy overview" - Apple Platform Security. https://support.apple.com/guide/security/apple-intelligence-security-overview-sec9a6b28146/web
12. "Apple's Private Cloud Compute: Analyzing the security of Apple's AI infrastructure" - Trail of Bits, Nov 2024. https://blog.trailofbits.com/2024/11/15/apples-private-cloud-compute-analyzing-the-security-of-apples-ai-infrastructure/
13. "Behind the scenes of Apple Intelligence: Security, privacy, and the user" - Apple Security Research, Feb 2025. https://security.apple.com/blog/behind-the-scenes-of-apple-intelligence/
14. "Apple and EU AI Act" - European Digital Rights (EDRi). https://edri.org/our-work/apple-and-the-eu-ai-act/
15. "Apple Intelligence: EU users gain access" - MacRumors. https://www.macrumors.com/2025/04/01/apple-intelligence-eu-users-gain-access/

**OpenAI**
1. "Moderation API" - OpenAI Platform Docs. https://platform.openai.com/docs/guides/moderation
2. "Safety best practices" - OpenAI Platform Docs. https://platform.openai.com/docs/guides/safety-best-practices
3. "Model Spec" - OpenAI. https://model-spec.openai.com
4. "Model Spec Evals" - OpenAI GitHub. https://github.com/openai/model-spec-evals
5. "gpt-oss-safeguard" - OpenAI GitHub. https://github.com/openai/gpt-oss-safeguard
6. "Agents SDK" - OpenAI GitHub. https://github.com/openai/openai-agents-python
7. "OpenAI Codex CLI" - OpenAI GitHub. https://github.com/openai/codex
8. "Swarm" - OpenAI GitHub (experimental). https://github.com/openai/swarm
9. "OpenAI o3 and o4-mini system card" - OpenAI Safety. https://safety.openai.com/system-cards/o3-o4-mini
10. "GPT-5.1 system card" - OpenAI Safety. https://safety.openai.com/system-cards/gpt-5
11. "Strong Rejection: Refusal classification with chain-of-thought" - OpenAI Research. https://openai.com/index/strong-rejection/
12. "Compliance API (Enterprise)" - OpenAI Platform Docs. https://platform.openai.com/docs/guides/compliance
13. "OpenAI Academy" - OpenAI. https://academy.openai.com
14. "EU AI Act compliance" - OpenAI. https://openai.com/global-affairs/eu-ai-act/
15. "OpenAPI traversal specification" - OpenAI. https://openai.com/index/openapi-traversal-specification/

**Anthropic**
1. "Constitutional Classifiers" - Anthropic Research, Jan 2026. https://www.anthropic.com/research/constitutional-classifiers
2. "Claude's Constitution" - Anthropic. https://docs.anthropic.com/en/docs/security-and-safety/claudes-constitution
3. "Claude Code permissions" - Anthropic Docs. https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/permissions
4. "Claude Code security" - Anthropic Docs. https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/security
5. "MCP (Model Context Protocol)" - Anthropic / Linux Foundation. https://www.modelcontextprotocol.com
6. "MCP specification (GitHub)" - Anthropic. https://github.com/modelcontextprotocol/specification
7. "Responsible Scaling Policy" - Anthropic. https://www.anthropic.com/news/responsible-scaling-policy-2
8. "Anthropic's Responsible Scaling Policy 2.0" - Anthropic. https://www.anthropic.com/research/responsible-scaling-policy-2-0
9. "Threat Intelligence at Anthropic" - Anthropic Research. https://www.anthropic.com/news/threat-intelligence
10. "Claude for Legal" - Anthropic Blog. https://www.anthropic.com/news/claude-for-legal
11. "Managed Agents API" - Anthropic Docs. https://docs.anthropic.com/en/docs/agents-and-tools/managed-agents
12. "Constitutional AI: Harmlessness from AI Feedback" - Anthropic Research (arXiv:2212.08073). https://arxiv.org/abs/2212.08073
13. "The Claude Model Context Protocol (MCP)" - Anthropic Blog, Nov 2024. https://www.anthropic.com/news/model-context-protocol
14. "Anthropic: The case for edge models" - Anthropic Research. https://www.anthropic.com/research/edge-models
15. "Brussels effect: How MCP donation to Linux Foundation shapes EU regulation" - TechCrunch / various. https://techcrunch.com/2025/04/15/anthropic-donates-mcp-to-linux-foundation/

**Meta**
1. "PurpleLlama GitHub Repository" - Meta. https://github.com/meta-llama/PurpleLlama (4.2k+ stars)
2. "Llama Guard 4 Model Card (12B)" - Meta / Hugging Face. https://github.com/meta-llama/PurpleLlama/blob/main/Llama-Guard4/12B/MODEL_CARD.md
3. "Llama Guard 2 Model Card (8B)" - Meta. https://github.com/meta-llama/PurpleLlama/blob/main/Llama-Guard2/MODEL_CARD.md
4. "CodeShield" - Meta LlamaFirewall docs. https://meta-llama.github.io/PurpleLlama/LlamaFirewall/docs/documentation/scanners/code-shield
5. "Sharing new open source protection tools and advancements in AI privacy and security" - Meta AI Blog, LlamaCon 2025. https://ai.meta.com/blog/ai-defenders-program-llama-protection-tools
6. "LlamaFirewall: An open source guardrail system for building secure AI agents" - Meta Research (arXiv:2505.03574). https://arxiv.org/html/2505.03574v1
7. "LlamaFirewall: Open-source framework to detect and mitigate AI centric security risks" - Help Net Security, May 2025. https://www.helpnetsecurity.com/2025/05/26/llamafirewall-open-source-framework-detect-mitigate-ai-centric-security-risks
8. "Meta AI at LlamaCon - Llama Guard 4, Llama Firewall, Prompt Guard 2" - AI at Meta @ X / Thread. https://x.com/AIatMeta/status/1917271400118902860
9. "Meta Launches Multi Agent Llama for Autonomous AI Systems" - Milaaj, Feb 2026. https://www.milaajdigitalacademy.com/insights/meta-multi-agent-llama-autonomous-ai
10. "Implement AI safeguards with Python and Llama Stack" - Red Hat Developer, Aug 2025. https://developers.redhat.com/articles/2025/08/26/implement-ai-safeguards-python-and-llama-stack
11. "Meta AI Agents: Llama Models Powering Open-Source AI Agents" - Nevo Systems, Feb 2026. https://nevo.systems/blogs/nevo-journal/meta-ai-agents
12. "Meta's Purple Llama tests AI models for safety risks" - IndiaAI. https://indiaai.gov.in/article/meta-s-purple-llama-tests-ai-models-for-safety-risks
13. "Firewalling Large Language Models with Llama Guard" - Kudelski Security, Jul 2025. https://kudelskisecurity.com/modern-ciso-blog/firewalling-large-language-models-with-llama-guard
14. "Meta Llama Guard 2 Model" - Hugging Face. https://huggingface.co/meta-llama/Meta-Llama-Guard-2-8B
15. "AutoGen Safety Configuration" - Authensor. https://www.authensor.com/learn/autogen-safety-configuration

---

## 5. Key Takeaways

1. **Anthropic leads on agent-level runtime safety** - Constitutional Classifiers++ is the only production deployment with documented 95%+ jailbreak resistance via a two-stage cascade architecture. Claude Code's permission model (three-tier auto mode, Plan Mode, read-only defaults, multi-agent handoff checks) is the most granular agent permission system available. The key gap is MCP's STDIO transport: 11 CVEs, 200K+ vulnerable instances, and ongoing protocol-level security debates (PROTOAMP, ATTESTMCP, SMCP proposals).

2. **Google/DeepMind has the most layered enterprise defense stack** - Model Armor's 5-layer architecture (non-configurable → system instructions → configurable thresholds → DLP → Gemini-as-Filter) is unique in its depth. Agent Identity (IAM principal per agent) and Agent Gateway (Apigee policy enforcement) are the most enterprise-grade agent access controls. The key weakness: no dedicated agent-specific safety framework comparable to LlamaFirewall or Constitutional Classifiers - relies on general-purpose Cloud security tooling.

3. **Apple has the strongest privacy-by-design guardrails** - on-device processing eliminates cloud attack surface for most operations; PCC provides verifiable transparency (public software images + audit logging); App Intents' schema-declared action surface makes it the only vendor where agents physically cannot exceed their declared capabilities. The key limitation: Foundation Models framework guardrail errors degrade UX (silent content blocking without user feedback); the closed ecosystem means no access to Apple's on-device safety classifiers for non-Apple developers.

4. **OpenAI has the best developer ergonomics and open-source safety tooling** - Moderation API (free, 6 categories), gpt-oss-safeguard (open-weight classifier), and Agents SDK (with `needsApproval`, safe-completions, strict mode) provide the most accessible safety toolkit. The Strong Rejection paper (CoT-based refusal) and Safety Reasoner represent cutting-edge research. Key gaps: tool guardrails only apply to hosted agents (not Codex CLI); audit logging is less granular than Google Cloud Audit Logs or Anthropic's handoff JSONL.

5. **EU AI Act strategies reveal fundamentally different regulatory philosophies**: Anthropic pursues the Brussels effect (MCP donated to Linux Foundation as a proto-EU standard). Apple's on-device architecture sidesteps cross-border data transfer concerns entirely. Google provides formal compliance frameworks (Assured Workloads EU Data Boundary, SecNumCloud 3.2, ISO 42001). OpenAI offers Compliance API + special access programs but has the least EU-specific infrastructure of the four.

6. **No single vendor covers the full agent safety lifecycle**: Anthropic leads on runtime safety + permission granularity but has protocol-level vulnerabilities. Google leads on enterprise governance + layered defense but lacks agent-specific safety frameworks. Apple leads on privacy + capability confinement but has a closed ecosystem. OpenAI leads on developer accessibility + open tooling but has the weakest audit and EU compliance posture. An optimal enterprise solution would combine Anthropic's permission model + Google's enterprise controls + Apple's privacy guarantees + OpenAI's developer tooling.

7. **Critical gaps across all four**: (a) Agent-to-agent communication security is unaddressed at the platform level - MCP has no standard for inter-agent authentication. (b) Multi-agent cascading failure detection is research-stage only. (c) Runtime behavior monitoring beyond input/output filtering is nascent - only Anthropic's task budgets (token accounting as behavioral monitoring) and Google's AI Control Loops (agent-in-the-middle) address this. (d) No vendor provides a unified audit trail across cloud + on-device + third-party agent deployments.
