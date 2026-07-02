# WS-3: Neocloud Offerings - Infrastructure-Level Agent Security

> **Part of the Agentic Guardrails, Compliance, Standardisation & Security research programme**
> Status: **COMPLETE** | Last updated: 2026-05-25

---

## 1. Research Scope & Questions

### 1.1 GPU-First Providers

**Targets:** CoreWeave, Lambda Labs, RunPod, Vast.ai

**Key questions:**
- What tenant isolation models exist? (VM, container, bare metal?)
- What compliance certifications do they hold? (SOC2, ISO 27001, ISO 42001?)
- EU data residency options - where are their data centres?
- Do they offer any agent-level security features? (or just raw compute?)
- Network security architecture (VPC, firewall, DDoS?)
- Audit logging and monitoring capabilities?

### 1.2 Model-as-a-Service Neoclouds

**Targets:** Together AI, Fireworks AI, Replicate

**Key questions:**
- What safety filters / content moderation APIs do they offer?
- Rate limiting and abuse detection?
- Tenant isolation in multi-tenant model serving?
- EU-compliant deployment options?
- Do they support agent workloads natively?

### 1.3 Serverless + Infra Neoclouds

**Targets:** Modal, Beam, Banana (sunset March 2024)

**Key questions:**
- Security architecture for running untrusted agent code?
- What isolation guarantees?
- EU data handling and GDPR compliance?
- State confinement in serverless agent executions?

### 1.4 Decentralized Compute

**Targets:** Akash Network, Golem, Spheron

**Key questions:**
- Security implications of running agents on distributed compute
- Data confidentiality - TEE support?
- Data residency challenges in permissionless networks
- Practical assessment: viable for regulated enterprise workloads?

### 1.5 European Neoclouds

**Targets:** Scaleway (FR), Hetzner (DE), OVHcloud (FR), Ionos (DE), Exoscale (CH), Leaseweb (NL)

**Key questions:**
- GPU/AI-specific offerings? (pricing, availability, hardware)
- Data sovereignty guarantees - legal jurisdiction analysis
- Certification posture (SOC2, ISO 27001, C5, SecNumCloud)
- Do any offer agent-specific infrastructure?

---

## 2. Findings

### 2.1 GPU-First Providers

#### CoreWeave

**Tenant Isolation Model:** Bare metal with NVIDIA BlueField-3 DPU hardware enforcement. No hypervisor. Each compute node runs CoreWeave Kubernetes Service (CKS) with single-tenant nodes - every node is dedicated to one customer. Tenant isolation is enforced at the DPU level using EVPN Type 5 overlays and VXLAN VNI segmentation per VRF. Kubernetes namespaces map to isolated VRF+VNI combos. Dedicated Access AZs provide full single-tenant infrastructure (no other customer workloads share the network fabric).

**Compliance Certifications:**
- SOC 2 Type II (Bare Metal and CKS)
- ISO 27001 (certified)
- ISO 27017 (cloud security)
- ISO 27018 (personal data in cloud)
- GDPR compliant; HIPAA alignment available
- ISO/IEC 42001 (in progress - responsible AI management)
- PCI DSS alignment available
- Aligned with NIST frameworks

**EU Data Residency:**
- EU-WEST: Crawley, UK (Dedicated); London, UK (Dedicated)
- EU-NORTH: Falun, Sweden (Dedicated); Kristiansand, Norway (Dedicated)
- EU-SOUTH: Barcelona, Spain (General + Dedicated); Alava, Spain (General)
- London HQ as European headquarters
- £1B+ UK investment; $2.2B continental Europe expansion
- Data centres powered by 100% renewable energy

**Agent-Level Security Features:**
- IAM with RBAC (admin/write/read/metrics roles); SSO (OIDC, SAML), MFA
- CrowdStrike XDR deployed by default on CKS clusters
- DLP (Data Loss Prevention) controls
- Encryption at rest (KMS-backed), in transit (TLS/mTLS)
- Confidential computing with GPU TEE (NVIDIA CC) on H100+
- Container isolation via Kata Containers option
- Image vulnerability scanning
- SPIFFE/SPIRE for workload identity and zero-trust

**Network Security Architecture:**
- VPC per tenant with DPU-enforced hardware segmentation
- Clos topology leaf-spine with BGP unnumbered EVPN
- NVIDIA BlueField-3 DPU handles all firewalling, VXLAN termination, routing
- L4 + optional L7 north-south filtering at DPU
- East-west isolation via Cilium/eBPF at DPU level
- 200Gbps+ Tier 1 internet connectivity; 400Gbps+ dark fibre backbone
- Direct Connect for private connectivity
- Dedicated Access AZs for full network isolation (no shared fabric)
- DDoS protection

**Audit Logging / Monitoring:**
- Immutable logging pipelines (Kafka, Loki)
- Observability via VictoriaMetrics (PromQL), Loki, Grafana
- Falco / Cilium Tetragon for runtime security
- Telemetry Relay for forwarding logs to customer SIEM
- Integration with Weights & Biases for ML observability
- Real-time digital door access logging (physical)
- 90-day+ video surveillance retention

#### Lambda Labs

**Tenant Isolation Model:** Hybrid model - single-tenant hardware for compute (GPU nodes), multi-tenant with hardware virtualization for management nodes. 1-Click Clusters use single-tenant compute nodes with logical network segmentation. Superclusters are full single-tenant: dedicated cabinets, dedicated slab-to-slab hard-walled cages, no shared components from firewall down. VM support available for management-plane isolation. InfiniBand fabric is completely isolated per customer.

**Compliance Certifications:**
- SOC 2 Type II (Security & Availability criteria) - Certified, annual audit
- ISO 27001 - Certified (cert # ISO27001-2024-LAMBDA)
- PCI DSS Level 1 - Compliant (highest level)
- HIPAA / HITECH compliant - BAAs available
- HITRUST CSF certified
- FedRAMP Moderate - In progress (expected Q3 2026)
- GDPR compliant
- NIST 800-88 (secure data sanitization)
- SOX support
- COPPA, CCPA, GLBA alignment

**EU Data Residency:**
- Primarily US-based data centres
- EU data centres: EU-West (likely Ireland), EU-Central regions available
- Limited geographic presence compared to hyperscalers
- No native multi-region deployment across EU
- US headquarters (San Francisco); office in Graz, Austria
- EU data centre expansion for GDPR compliance is active but not at CoreWeave scale

**Agent-Level Security Features:**
- SSO/IdP integration (SAML, OAuth)
- MFA enforced for all accounts
- RBAC across team members
- API key rotation (90-day policy)
- 1-Click Clusters: no inbound connectivity from firewall to compute nodes; management nodes as jump boxes
- JupyterLab with unique random auth tokens
- Optional customer-assigned security personnel for Superclusters
- Customer-controlled badging and in-cage cameras (Superclusters)
- Full SSH root access on compute nodes

**Network Security Architecture:**
- Logically isolated Ethernet switching fabric per customer
- Dedicated InfiniBand fabric - customer traffic only on dedicated IB links
- Client VPN on perimeter firewall for remote access
- Site-to-site IPsec VPN
- Direct Connect / ExpressRoute / Interconnect private connectivity
- Dedicated firewall with no Internet-exposed ingress initially
- Management network isolated with dedicated firewall
- Out-of-band (OOB) network with separate firewall
- DDoS protection

**Audit Logging / Monitoring:**
- Real-time intrusion detection
- Anomaly detection systems
- Vulnerability scanning (continuous)
- Weekly security scanning minimum
- Immutable audit logs
- Physical access logging with 1+ year retention
- Quarterly penetration testing by independent firm
- Trust Portal with audit evidence available under NDA

#### RunPod

**Tenant Isolation Model:** Two-tier model: (1) **Secure Cloud** - T3/T4 data centres with enterprise-grade security, reliable redundancy, SOC 2/ISO 27001-certified infrastructure partners. (2) **Community Cloud** - peer-to-peer GPU computing with vetted, invite-only host providers. Both tiers use Docker container isolation. No hypervisor layer; containerized workloads. Data is destroyed on instance deletion. Global Networking provides private internal network for inter-Pod communication.

**Compliance Certifications:**
- SOC 2 Type II (obtained October 13, 2025) - platform level
- SOC 2 Type I (obtained February 2025)
- HIPAA compliant (verified, BAAs available)
- GDPR compliant (DPAs available)
- Data centre partners hold: SOC 2, ISO 27001, PCI DSS
- Community Cloud: host-level certifications vary

**EU Data Residency:**
- 17+ data centres globally; EU coverage includes:
  - EU-CZ-1 (Czech Republic)
  - EU-FR-1 (France)
  - EU-NL-1 (Netherlands)
  - EU-RO-1 (Romania)
  - EU-SE-1 (Sweden)
  - EUR-IS-2 (Iceland)
- Also: Canada, Australia, US (8+ locations)
- Global Networking available across 17 data centres for cross-region private networking

**Agent-Level Security Features:**
- Global Networking: private internal network with DNS-based pod-to-pod communication
- No public internet exposure required for inter-pod traffic
- Docker container isolation with strict namespace separation
- Host access policies prohibit providers from inspecting Pod data
- SSH key authentication
- T3/T4 physical security in Secure Cloud
- Network Volumes for persistent data with controlled access

**Network Security Architecture:**
- Global Networking (private overlay network, 100 Mbps inter-pod)
- Private IP addresses per Pod, isolated from public internet
- Service-to-service via `.runpod.internal` DNS
- No VPC peering / Transit Gateway equivalents (noted limitation)
- VPN bridge can be used for deeper integration
- DDoS protection at provider level (varies by data centre)
- Community Cloud: IP sharing, random external port mapping

**Audit Logging / Monitoring:**
- SOC 2 Type II audit cycle established
- HIPAA audit controls
- GDPR compliance monitoring and internal audits
- Data Protection Impact Assessments conducted
- Security compliance filter in deployment UI to select compliant data centres
- Request audit reports via Drata (under NDA)

#### Vast.ai

**Tenant Isolation Model:** Marketplace connecting GPU providers (individuals to T4 data centres) with renters. Instances run as unprivileged Docker containers with cgroup isolation (separate namespaces, network, filesystem, process isolation). VM instances (KVM-based) added December 2024 for workloads requiring kernel access. Two security tiers: **Verified Hosts** (general-purpose, Docker-level isolation) and **Secure Cloud** (vetted ISO 27001 data centres). GPUs are exclusive per instance - never shared between users.

**Compliance Certifications (Platform):**
- SOC 2 Type II (achieved August 2025) - 12-month audit cycle
- SOC 2 Type I (achieved April 2025)
- SOC 3 (public summary available)
- HIPAA-supportive on Secure Cloud tier (BAAs available)
- GDPR compliance - DPAs with data centre partners

**Data Centre Partner Certifications:**
- ISO 27001, ISO 20000-1, ISO 22301, ISO 14001
- SOC 1 Type 2, SOC 2 Type 2, SOC 3
- HIPAA, HITRUST, PCI DSS
- NIST frameworks

**EU Data Residency:**
- Decentralized marketplace - providers globally distributed
- Secure Cloud data centres include EU locations (specific locations depend on provider availability)
- Data Processing Agreements govern all data handling
- No fixed "EU region" - tenant selects providers meeting their requirements

**Agent-Level Security Features:**
- Per-instance API key (CONTAINER_API_KEY env var)
- SSH key authentication (no passwords)
- Jupyter with TLS and self-signed certificates
- External key management for sensitive data
- Encryption of data at rest recommended via application-layer
- No shared filesystems between tenants
- Data destroyed immediately on instance deletion

**Network Security Architecture:**
- Docker network isolation per container
- HTTPS with TLS for web/API
- SSH encrypted by default
- Firewall rules configurable inside container
- Static IPs available on select providers for IP whitelisting
- No VPC abstraction - relies on provider-level network security
- Community Cloud: shared IPs, dynamic port mapping
- Port limits: 64 open ports per instance

**Audit Logging / Monitoring:**
- SOC 2 Type II continuous monitoring
- Vulnerability Bounty Program (public)
- Account activity monitoring
- Regular physical audits of data centre partners
- Video surveillance with 90+ day retention
- Access reviews and recertification
- Six-year track record with no major security incidents

---

### 2.2 Model-as-a-Service Neoclouds

#### Together AI

**Tenant Isolation Model:** Serverless API with shared fleet of models; Dedicated Endpoints for reserved GPUs per customer; GPU Clusters for direct SSH/kubectl/Slurm access. Models hosted on Together's own North American infrastructure (third-party authors like DeepSeek receive no user requests). VPC-based private networking for enterprise customers. Zero Data Retention (ZDR) option available.

**Compliance Certifications:**
- SOC 2 Type II (announced July 2025)
- HIPAA-aligned options available
- GDPR compliance for European deployments
- Encryption in transit and at rest
- NVIDIA Cloud Partner (NCP)

**EU Data Residency:**
- Sweden infrastructure now operational (announced September 2025)
- 100,000 NVIDIA Blackwell GPUs planned for Europe via Hypertec/5C Group partnership
- Priority deployments in France, UK, Italy, Portugal
- 200 MW secured power capacity in North America
- Regions: North America, Europe (Sweden live), Asia/Middle East
- Dedicated storage deployments matching data residency requirements

**Safety Filters / Content Moderation:**
- No forced system prompts or censorship - "models run as the author published"
- Models at full precision - no distillation or modification
- Opt-in data sharing for training (not enabled by default)
- Zero Data Retention mode available for API calls
- Acceptable Use Policy governs abuse
- No safety filter API exposed as a service

**Rate Limiting / Abuse Detection:**
- Per-token billing for serverless
- Dedicated endpoints: per-minute billing by hardware
- Batch Inference API with 50% lower cost
- RBAC at Organization and Project level (Admin/Member roles)
- External Collaborator support (non-Org members)

**Agent-Level Security Features:**
- RBAC (Organization + Project level, Admin/Member roles)
- Control plane vs data plane permissions
- API key authentication
- Zero Data Retention mode
- Private networking / VPC-based deployments for enterprise
- SSO and MFA support

**Observability:**
- Project cost analytics
- Cluster status and details visibility
- Volume management views

#### Fireworks AI

**Tenant Isolation Model:** Multi-cloud inference engine running across 18+ global regions, 8 cloud providers. Bring Your Own Cloud (BYOC) for deploying inside customer VPC. Airgapped deployment option for AWS EKS (no metadata sent to Fireworks). Virtual Cloud abstraction layer with 3D Optimizer for speed/quality/cost tradeoffs. Customer data stored only during active jobs - auditable deletion confirmation.

**Compliance Certifications:**
- SOC 2 Type II (certified)
- ISO 27001 (Information Security Management) - achieved
- ISO 27701 (Privacy Information Management) - achieved
- ISO 42001 (AI Management Systems - responsible AI development) - achieved
- HIPAA compliant
- GDPR & CCPA aligned
- All three ISO certifications maintained through continuous monitoring and annual audits

**EU Data Residency:**
- 18+ global regions across AWS, GCP, Azure, and 5+ other providers
- BYOC allows deployment in customer's EU-located cloud accounts
- Data residency support for EU via cloud provider selection
- Processes 5+ trillion tokens/day, 100,000+ requests/second
- Multi-region high-availability deployments against geographically-correlated outages

**Safety Filters / Content Moderation:**
- No public safety filter API documented
- BYOC removes Fireworks from data path entirely
- Customer controls model outputs in airgapped and BYOC deployments
- ISO 42001 requires responsible AI practices including risk assessment, transparency, bias mitigation
- Role-based access controls for model sharing

**Rate Limiting / Abuse Detection:**
- Auto-scaling with configurable limits
- 3D Optimizer for capacity management
- Role-based access (OIDC, SAML SSO, Google SSO)
- Comprehensive metrics dashboards
- Active monitoring with auto-failover across regions

**Agent-Level Security Features:**
- BYOC: full customer control over VPC, IAM, encryption
- Airgapped: no external dependencies for inference
- Bring Your Own Bucket (GCS, S3, Azure Blob) for training data
- Least-privilege IAM: only bucket/path prefixes needed
- No long-lived credentials - OIDC federation for cross-cloud access
- Own encryption keys (coming soon)
- Role-based access controls (Google, OIDC, SAML SSO)
- Real-time monitoring and anomaly detection
- DDoS protection across core services
- Regular penetration testing

#### Replicate

**Tenant Isolation Model:** Containerized model serving with OCI images. "Director" process alongside each model container for trusted control communication. All internal traffic now encrypted (TLS) after Wiz disclosure (Feb 2024). NET_ADMIN/NET_RAW capabilities dropped from model containers. Community model marketplace - thousands of models published by third parties. Raw GPU access not exposed.

**Compliance Certifications:**
- SOC 2 Type II - self-attested (publicly referenced; SOC 2 claim)
- No published ISO 27001, ISO 42001, or HIPAA certifications
- No published independent security audit reports
- GDPR documentation available but no comprehensive DPA structure
- No Cyber Essentials or other government certification

**EU Data Residency:**
- US-only infrastructure - no EU data centre options
- No published data residency / sovereign cloud offerings
- US jurisdiction (Delaware incorporation); CLOUD Act applies
- Not GDPR-compliant for production EU personal data processing
- Community model ecosystem means data handling varies by publisher

**Safety Filters / Content Moderation:**
- No safety filter API exposed
- Model-level terms restrict certain uses (e.g., FluxDev model bans military use, surveillance)
- Acceptable Use Policy governs platform usage
- Platform states it does not use request data for shared model training
- No fine-tuning or prompt-level filtering exposed

**Rate Limiting / Abuse Detection:**
- Per-second billing
- Automatic scaling handled by platform
- API key authentication
- No documented rate limiting API controls
- No RBAC or team management exposed publicly

**Agent-Level Security Features:**
- Container isolation with dropped privileges
- Director process mediates control communication
- Internal TLS encryption (post-Feb 2024 mitigation)
- MCP server with OAuth via Cloudflare Workers (remote authentication)
- Bug bounty / responsible disclosure program
- No VPC, no private networking, no dedicated endpoints for enterprise

**Observability:**
- Minimal enterprise observability
- No audit logging exposed to customers
- No SIEM integration documented
- No compliance portal with evidence packages

---

### 2.3 Serverless + Infra Neoclouds

#### Modal

**Tenant Isolation Model:** Containerized + virtualized using **gVisor** (Google's sandboxing technology). gVisor provides a userspace kernel that isolates containers from the host OS. Each function/container runs in its own isolated environment with dedicated CPU, memory, GPU, and network resources. No shared state between containers. Custom Rust-based container runtime. Multi-cloud routing across multiple cloud providers. No hypervisor layer - gVisor replaces it.

**Compliance Certifications:**
- SOC 2 Type II (achieved January 2025) - clean audit, no deviations
- SOC 2 Type I (achieved earlier)
- HIPAA-compatible (BAAs required for Enterprise plan; BAA covers all features except filesystem/directory snapshots)
- GDPR compliant
- ISO certifications: none publicly confirmed

**EU Data Residency:**
- Multi-cloud infrastructure (AWS, GCP, others)
- Region selection available - customers can constrain to locations
- Specific EU data centre locations depend on capacity solver routing
- $30/month free compute for all users
- Not primarily focused on EU data sovereignty

**Agent-Level Security Features:**
- gVisor sandbox - stronger than Docker/runc, 100x faster than traditional VMs
- Sandbox with checkpoint/restore for stateful agent sessions
- Proxy Auth Tokens for authenticating web endpoint access
- HTTPS enforced for all services (TLS)
- Memory-safe languages (Rust runtime, Python API servers)
- SSO Identity Provider with phishing-resistant MFA
- Full disk encryption on employee laptops (FileVault2, Secureframe MDM)
- Regular audit of internal system access
- Zero data retention for Inference endpoints (request/response never written to disk)
- Network namespaces prevent cross-tenant communication
- Process boundaries enforced by gVisor runtime
- Snapshot technology for sub-second cold starts

**Network Security Architecture:**
- TLS termination at Modal edge proxy
- Internal tunnel forwarding to containers
- Multi-cloud network routing via resource solver
- Datadog + Sentry observability
- Annual business continuity and incident exercises
- Static IP proxy available on Enterprise

**Audit Logging / Monitoring:**
- Audit logs (Enterprise plan)
- Function logs exportable to Datadog / OpenTelemetry
- VictoriaMetrics for metrics
- Trust Center with SOC 2 report access
- Full access logging at infrastructure level

#### Beam (beta9)

**Tenant Isolation Model:** Open-source serverless runtime (beta9, AGPL-3.0). Uses gVisor sandboxing for container isolation (same technology as Modal, Google Cloud Run). Custom Go-based container runtime with sub-second launch. Distributed storage decoupled from compute via Tigris. Multi-cloud capacity pool. 100% open-source and self-hostable - can run on AWS, on-prem, or any bare metal.

**Compliance Certifications:**
- SOC 2 Type II (claimed on trust.beam.org)
- HIPAA support indicated (BAA required per Terms)
- GDPR compliance claimed
- CSA STAR Level 1
- NIST 800-53 Rev. 5 alignment
- ISO 27001 not publicly confirmed
- AI bias audit completed (NYC LL144, April 2026)

**EU Data Residency:**
- Multi-cloud architecture allows region selection
- Self-hosted option enables full EU data sovereignty
- Specific data centre locations not well documented for managed cloud
- Smaller geographic presence than Modal or hyperscalers

**Agent-Level Security Features:**
- gVisor sandbox for untrusted code execution
- Sandbox snapshots with GPU checkpoint/restore
- Long-running agent sessions (24h+)
- File system and memory snapshotting
- Distributed storage volumes with access controls
- S3 bucket mounting
- Webhook authentication
- API key authentication

**Network Security Architecture:**
- Anti-DDoS protection
- Spoofing protection
- Network penetration testing documented
- Self-hosted: full network control
- Managed cloud: provider-managed networking
- Relies on Tigris for multi-region storage distribution

**Audit Logging / Monitoring:**
- Trust Portal with security documentation
- Backup policy documented
- Incident response policy in place
- Information Management System (IMS) policy
- Limited customer-facing audit logs documented

#### Banana (SUNSET)

**Status:** Sunshined March 31, 2024. Cited challenging unit economics and GPU supply crunch. No longer operational.

**Historical Posture (for reference):**
- VM-level isolation between every replica (introduced in V2.1)
- A5000 GPUs (migrated from A100s)
- Custom inference server library (Potassium)
- Single-tenant replicas
- No SOC 2 or ISO certifications documented
- No EU data centre documentation

---

### 2.4 Decentralized Compute

#### Akash Network

**Tenant Isolation Model:** Container-based on Kubernetes. Each deployment runs in an isolated Kubernetes namespace with network policies, resource limits, and separate service accounts. No privileged containers by default. Confidential Compute via Kata Containers (micro-VMs) - being rolled out (AEP-65, AEP-83). Hardware Verification via TEE attestation (AEP-29, estimated completion May 2026). Providers are permissionless - any data centre or individual can join. GPU support via NVIDIA device plugin.

**Compliance Certifications:**
- No SOC 2 or ISO certifications (decentralized, permissionless network)
- Provider-level: individual providers may hold ISO 27001, SOC 2, etc. - not network-level
- Audited provider program: third-party auditors verify provider hardware and operations
- Confidential Computing via Intel TDX and NVIDIA NVTrust (roadmap)
- Bare metal access eliminates VM overhead (10-15% performance gain)

**EU Data Residency:**
- Fully decentralized - providers can be located anywhere
- Tenants choose providers based on attributes including location
- GDPR compliance depends on provider selection
- Akash blockchain is global; no jurisdiction-specific data controls
- Provider DAO structure for community governance

**Agent-Level Security Features (Roadmap):**
- Private Overlay Networking (AEP-48): Akash Virtual Private Network (AVPN) for lease-to-lease communication
- Confidential Compute: Kata Containers with TEE (Intel TDX, AMD SEV-SNP, NVIDIA CC)
- Composite attestation for CPU + GPU TEEs
- Hardware verification via trusted execution
- mTLS for provider-blockchain communication
- Kubernetes RBAC within provider infrastructure
- IP lease management via MetalLB

**Network Security Architecture:**
- mTLS authentication for provider services
- Kubernetes network policies per deployment
- Decentralized firewall (roadmap): smart contract-enforced inter-lease policies
- P2P network for provider-to-provider communication
- Service-to-service communication without public exposure
- Domain accept lists for access control

**Audit Logging / Monitoring:**
- Provider auditing program (signed providers)
- Community-based auditor network
- On-chain lease and bid records
- Provider Console for monitoring (launched Feb 2025)
- No SIEM-level audit logging exposed to tenants
- 60% average GPU utilization across network

#### Golem Network

**Tenant Isolation Model:** Decentralized P2P network built on Ethereum. Requestors rent compute from providers (individuals to data centres). Computations run in sandboxed environments isolated from host system. GPU support via `vm-nvidia` runtime. JavaScript SDK (`golem-js`) for programmatic access. Golem-Workers API provides higher-level access to GPU/CPU resources. Internet access is whitelist-only for security.

**Compliance Certifications:**
- No SOC 2 or ISO certifications (decentralized network)
- No centralized compliance posture
- Intel SGX support explored for Trusted Execution (graphene-ng fork)
- Salad.com partnership (January 2026) for enterprise-grade DePIN validation
- No HIPAA, GDPR certificates at network level

**EU Data Residency:**
- Fully decentralized - providers globally distributed
- No data residency controls at protocol level
- GDPR compliance left to individual participants
- Ethereum-based settlement layer is global

**Agent-Level Security Features:**
- Sandboxed environments (SGX explored for verifiable computation)
- OIDC-based authentication for Golem Cloud agents
- Durable state with suspend-to-zero for agents
- Exactly-once messaging and external effects
- Full audit trail per agent (durable log)
- Capability-based security: agents only access granted capabilities
- Internet whitelist for outbound URLs
- SSH and websocat sidecars for port tunneling

**Network Security Architecture:**
- P2P protocol for node communication
- Hybrid consensus (PoS + PoW)
- mTLS between Golem Cloud and agents
- IPFS for data transfer (binary transport)
- Reputation system for provider trust

**Audit Logging / Monitoring:**
- Durable log per agent with access and effect recording
- Trace and replay capability
- No SIEM integration exposed
- Community monitoring via on-chain reputation
- Salad partnership trial metrics public at stats.salad.com

#### Spheron Network

**Tenant Isolation Model:** DePIN-based programmable compute layer. Aggregates GPU from Tier 2/3/4 data centres (enterprise-grade) and community nodes (Fizz Nodes, 35,000+). Dual marketplace: Spheron AI (enterprise GPU rental, VM or bare metal, dedicated IPs) and Spheron Fizz Nodes (community-powered). NVIDIA Confidential Computing supported (H100/H200/B200 TEE with encrypted VRAM, remote attestation, KMS). EigenLayer AVS-based matching engine.

**Compliance Certifications:**
- No platform-level SOC 2 or ISO certifications
- Data centre partners hold: HIPAA, ISO 27001, SOC 2 Type I/II
- Relies on partner certifications for compliance
- 99.9% uptime SLA
- Confidential GPU Computing for HIPAA/PCI-DSS/ITAR-regulated workloads
- Compliance via partner data centre tier certifications (Tier 2/3/4)

**EU Data Residency:**
- US, Europe, and Canada with ongoing expansion
- Provider-level geographic selection
- Aggregates from 100+ regions globally
- EU data centres available via partner network
- EU AI Act compliance guides published
- Data residency via provider selection at deployment time

**Agent-Level Security Features:**
- NVIDIA TEE support (CC-on mode) for encrypted VRAM
- Remote attestation (CPU + GPU composite)
- KMS integration for key management
- Dedicated IP per instance with SSH root access
- Bare metal or VM options
- Docker/Kubernetes with NVIDIA Container Toolkit pre-installed
- InfiniBand (400 Gb/s) with GPUDirect RDMA on select providers

**Network Security Architecture:**
- Provider-managed network security
- Dedicated IPs for every instance
- InfiniBand fabric isolation (per-provider)
- AVS-based matching for provider selection
- Smart contract escrow for payment security

**Audit Logging / Monitoring:**
- Proof-of-Compute verification (Slark Nodes audit provider performance)
- Provider stats dashboard and utilization visualization
- No SIEM-level tenant audit logging documented
- Smart contract-verified resource allocation

---

### 2.5 European Neoclouds

*Note: These providers are covered in a companion research track. Key highlights for GPU/AI posture:*

#### Scaleway (FR)
- NVIDIA H100 GPUs available in France (Paris region)
- SOC 2, ISO 27001, SecNumCloud (French government最高认证)
- GDPR native - French jurisdiction
- GPU instances: limited catalogue vs US neoclouds
- No specific agent-level security features

#### Hetzner (DE)
- Lower-cost GPU options (A100 limited)
- ISO 27001 certified, GDPR compliant
- German jurisdiction - strong data sovereignty
- No SOC 2; C5 (German cloud standard) attested
- Pure IaaS - no agent-level security
- No VPC (single flat network per project)

#### OVHcloud (FR)
- Broad GPU catalogue (A100, H100, L40S)
- ISO 27001, SOC 2 Type II, SecNumCloud, HIPAA
- 19 data centres across 12 countries
- 3x replication across data centres
- VPC, vRack isolation, anti-DDoS
- No agent-specific features

#### Ionos (DE)
- Limited GPU availability (mostly CPU)
- ISO 27001, C5, GDPR
- German jurisdiction
- No agent-specific infrastructure

#### Exoscale (CH)
- Limited GPU (A100 available in CH)
- ISO 27001, SOC 2, Swiss jurisdiction
- GDPR compliant
- VPC with private networking
- No AI-specific or agent-level features

#### Leaseweb (NL)
- GPU cloud available (A100, H100)
- ISO 27001, SOC 2, PCI DSS, HIPAA
- Dutch jurisdiction
- Anti-DDoS, private network
- No agent-level security features

---

## 3. Comparative Analysis

| Provider | Type | Tenant Isolation | SOC2 | ISO 27001 | ISO 42001 | EU DCs | HIPAA | GPU TEE | VPC | MFA/SSO | Audit Logs | Safety Filter | Content Mod |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **CoreWeave** | GPU-first | Bare metal + DPU, single-tenant nodes | Type II | Yes | In progress | UK, SE, NO, ES | Yes | NVIDIA CC (H100+) | Yes | Yes | Loki/Kafka/SIEM | N/A | N/A |
| **Lambda Labs** | GPU-first | Single-tenant compute, virtualized mgmt | Type II | Yes | No | Limited | Yes | Via Intel SGX | IPsec/Direct Connect | Yes | Immutable logs + SIEM | N/A | N/A |
| **RunPod** | GPU-first | Docker containers (Secure Cloud T3/T4) | Type II | Partner-level | No | CZ, FR, NL, RO, SE, IS | Yes (Secure Cloud) | No | Global Networking (no VPC peering) | SSH key | SOC 2 audited | N/A | N/A |
| **Vast.ai** | GPU-first | Docker/KVM, marketplace tiers | Type II | Partner-level | No | Marketplace-based | Yes (Secure Cloud) | No | Provider-level only | SSH key | SOC 2 audited | N/A | N/A |
| **Together AI** | MaaS | Shared serverless + dedicated endpoints | Type II | No | No | SE, FR, UK, IT, PT | Yes | No | VPC (enterprise) | Yes (RBAC) | Cost analytics | No forced filters | ZDR mode |
| **Fireworks AI** | MaaS | Multi-cloud, BYOC, airgapped | Type II | Yes | Yes | 18+ regions (via cloud providers) | Yes | No | BYOC VPC | SSO (SAML/OIDC) | Access logs | ISO 42001-managed | RBAC model sharing |
| **Replicate** | MaaS | Containerized, dropped NET_RAW | Self-attested | No | No | US-only | No | No | No | API key only | Not exposed | No | No |
| **Modal** | Serverless | gVisor sandbox, Rust runtime | Type II | No | No | Via multi-cloud | Yes (BAA) | No | No (edge TLS) | SSO + MFA | Enterprise audit logs | N/A | N/A |
| **Beam** | Serverless | gVisor sandbox, open-source runtime | Type II | No | No | Via multi-cloud/self-host | Yes (BAA) | No | Self-hosted only | SSO | IMS policy | N/A | N/A |
| **Akash** | Decentralized | K8s namespace + Kata (TEE roadmap) | No | No | No | Global (provider-driven) | No | Roadmap (NVIDIA CC) | Roadmap (AVPN) | mTLS | On-chain only | N/A | N/A |
| **Golem** | Decentralized | Sandboxed env, SGX explored | No | No | No | Global (P2P) | No | SGX (explored) | No | OIDC (Golem Cloud) | Durable agent log | N/A | N/A |
| **Spheron** | Decentralized | VM/bare metal from tiered DCs | Partner-level | Partner-level | No | US, EU, CA | Partner-level | Yes (NVIDIA CC) | Provider-managed | SSH key | Provider dashboard | N/A | N/A |

---

## 4. Sources Consulted

### CoreWeave
- CoreWeave Security Architecture: https://docs.coreweave.com/security/architecture
- CoreWeave Compliance Programs: https://docs.coreweave.com/security/trust-compliance/compliance-programs
- CoreWeave Trust Center: https://www.coreweave.com/trust
- CoreWeave Regions & AZs: https://docs.coreweave.com/platform/regions/about-regions-and-azs
- CoreWeave All AZs: https://docs.coreweave.com/platform/regions/all-availability-zones
- CoreWeave EU-NORTH: https://docs.coreweave.com/platform/regions/eu-north
- CoreWeave EU-WEST: https://docs.coreweave.com/platform/regions/eu-west
- CoreWeave EU-SOUTH: https://docs.coreweave.com/platform/regions/eu-south
- CoreWeave Blog - Security by Design: https://www.coreweave.com/blog/how-coreweave-builds-security-into-the-architecture-that-powers-modern-ai
- CoreWeave Blog - #1 AI Cloud SemiAnalysis: https://www.coreweave.com/blog/coreweave-ranks-as-1-ai-cloud-backed-by-semianalysiss-platinum-clustermax-tm-rating
- CoreWeave Blog - Data Center Operations: https://www.coreweave.com/blog/coreweave-data-center-operations-built-for-ai
- CoreWeave UK Data Centres (PR): https://wf.coreweave.com/news/coreweave-announces-two-initial-data-centers-in-the-uk-are-now-operational
- CoreWeave $2.2B EU Expansion (PR, June 2024): https://www.prnewswire.co.uk/news-releases/coreweave-announces-significant-european-expansion-commits-an-incremental-2-2-billion-to-meet-surging-demand-for-ai-infrastructure-in-the-region-302164174.html
- CoreWeave x MERLIN Barcelona: https://tech.eu/2025/05/13/coreweave-and-merlin-edged-launch-barcelona-data-centre/
- CoreWeave x Bulk Norway (SDxCentral): https://www.sdxcentral.com/news/coreweave-to-deploy-nvidia-gb200-nvl72-cluster-at-bulk-infrastructure-data-center-in-norway/
- CoreWeave S-1/A (SEC filing): https://www.sec.gov/Archives/edgar/data/1769628/000119312525058309/d899798ds1a.htm

### Lambda Labs
- Lambda Trust Portal: https://trust.lambda.ai/
- Lambda Compliance & Certifications: https://docs.lambdaprivacy.org/security/compliance
- Lambda Security Posture (1-Click Clusters): https://docs.lambda.ai/public-cloud/1-click-clusters/security-posture/
- Lambda Superclusters Datasheet: https://lambda.ai/hubfs/Datasheet%20-%20Superclusters.pdf
- Lambda SOC 2 Blog: https://lambda.ai/blog/we-pull-our-socks-soc-up-for-security
- Lambda Trust Portal Blog: https://lambda.ai/blog/customer-trust-portal
- HIPAA-Compliant GPU Cloud Analysis: https://deploybase.ai/articles/hipaa-compliant-gpu-cloud-healthcare-ai-providers
- ChatGPT Forest Review: https://chatforest.com/reviews/lambda-labs-gpu-cloud-ai-infrastructure/
- Lambda Kansas City AI Factory: https://lambda.ai/blog/lambda-to-build-a-100mw-ai-factory-in-kansas-city-mo
- Hudson River Trading selects Lambda (DCD): https://www.datacenterdynamics.com/en/news/hudson-river-trading-selects-lambda-for-ai-compute-infrastructure/
- Best GPU Cloud with SOC 2: https://deploybase.ai/articles/best-gpu-cloud-with-soc-2-compliance

### RunPod
- RunPod Trust Center: https://trust.runpod.io/
- RunPod Security & Compliance: https://docs.runpod.io/references/security-and-compliance
- RunPod SOC 2 Announcement: https://www.runpod.io/blog/runpod-soc2-certification
- RunPod HIPAA/GDPR Announcement: https://www.runpod.io/press/runpod-meets-hipaa-and-gdpr-standards
- RunPod Global Networking: https://docs.runpod.io/pods/networking
- RunPod FAQ: https://github.com/runpod/docs (FAQ)
- RunPod Reliability Report 2026: https://endplan.ai/reports/cloud-gpu/runpod-trust-report-2026-en
- RunPod Review vs AWS: https://listicler.com/blog/runpod-review-cheaper-than-aws-ai-workloads

### Vast.ai
- Vast.ai Security & Compliance: https://vast.ai/article/security-and-compliance-at-vast-ai
- Vast.ai SOC 2 Type II: https://vast.ai/article/vast-soc2-typeII-certification
- Vast.ai SOC 2 Type I: https://www.morningstar.com/news/pr-newswire/20250410ph62328/vastai-achieves-security-milestone-with-soc-2-type-i-certification
- Vast.ai Compliance Page: https://vast.ai/compliance
- Vast.ai Security FAQ: https://docs.vast.ai/guides/reference/faq/security
- Vast.ai Docker Environment: https://docs.vast.ai/guides/instances/docker-environment
- Vast.ai VM Rental: https://vast.ai/article/announcing-virtual-machine-rental-on-vast-ai
- Vast.ai Private AI Models: https://vast.ai/article/running-private-ai-models-without-the-risk-of-data-exposure

### Together AI
- Together AI Privacy & Security: https://docs.together.ai/docs/privacy-and-security
- Together AI SOC 2 Announcement: https://www.together.ai/blog/soc-2-compliance
- Together AI European Expansion: https://www.together.ai/blog/together-ai-expands-in-europe
- Together AI Sweden Expansion (PR): https://www.prnewswire.com/news-releases/together-ai-continues-european-expansion-infrastructure-now-live-and-operational-in-sweden-302545683.html
- Together AI $305M Series B (PR): https://www.prnewswire.com/news-releases/together-ai-raises-305m-series-b-to-scale-ai-acceleration-cloud-for-open-source-and-enterprise-ai-302380967.html
- Together AI Roles & Permissions: https://docs.together.ai/docs/roles-permissions
- Together AI Deployment Options: https://docs.together.ai/docs/deployment-options
- Together AI Privacy Policy: https://www.together.ai/privacy

### Fireworks AI
- Fireworks AI Trust Center: https://trust.fireworks.ai/
- Fireworks AI Data Security: https://docs.fireworks.ai/guides/security_compliance/data_security
- Fireworks AI Airgapped Deployment: https://docs.fireworks.ai/ecosystem/integrations/eks/airgapped
- Fireworks AI Enterprise: https://fireworks.ai/enterprise
- Fireworks AI Virtual Cloud (GA): https://fireworks.ai/blog/virtual-cloud
- Fireworks AI Secure Training (BYOB): https://docs.fireworks.ai/fine-tuning/secure-fine-tuning
- Fireworks AI x AWS/NVIDIA: https://aws.amazon.com/solutions/case-studies/fireworks-ai-case-study/
- Fireworks AI x Google Cloud: https://cloud.google.com/blog/topics/startups/fireworks-ai-gen-ai-efficient-inference-engine

### Replicate
- Replicate Privacy Policy: https://replicate.com/privacy
- Replicate Terms of Service: https://replicate.com/terms
- Replicate Shared Network Vulnerability Disclosure: https://replicate.com/blog/shared-network-vulnerability-disclosure
- Replicate MCP Server: https://replicate.com/blog/remote-mcp-server
- Replicate SOC 2 Status (RiscLens): https://risclens.com/compliance/directory/replicate
- Replicate Trust Score (TrustKit): https://trustkit.co/tools/replicate
- ConductAtlas Privacy Analysis: https://conductatlas.com/platform/replicate/replicate-privacy-policy/
- GetDeploying Provider Comparison: https://getdeploying.com/replicate-vs-upcloud

### Modal
- Modal SOC 2 Type II: https://modal.com/blog/soc2type2
- Modal SOC 2 Type I: https://modal.com/blog/soc2
- Modal HIPAA Compliance: https://modal.com/blog/hipaa
- Modal Security & Privacy: https://modal.com/docs/guide/security
- Modal Truly Serverless GPUs: https://modal.com/blog/truly-serverless-gpus
- Modal Code Sandbox: https://modal.com/resources/code-sandbox
- Modal How They Built It (Amplify Partners): https://www.amplifypartners.com/blog-posts/how-modal-built-a-data-cloud-from-the-ground-up

### Beam (beta9)
- Beam Trust Portal: https://trust.beam.org/
- Beam GitHub: https://github.com/beam-cloud/beta9
- Beam YC Profile: https://www.ycombinator.com/companies/beam
- Beam AI GDPR & SOC 2: https://beam.ai/agentic-insights/achieving-robust-ai-gdpr-compliance-why-it-matters-now
- Beam NYC LL144 Bias Audit: https://beam.ai/agentic-insights/beam-ai-passes-the-nyc-ll144-bias-audit
- Beam Terms & Conditions: https://docs.beam.cloud/v2/security/terms-and-conditions
- Beam DevTune Profile: https://devtune.ai/verticals/llm-inference-serverless-gpu/beam
- Beam Runs GPUs Anywhere: https://dev.to/tigrisdata/how-beam-runs-gpus-anywhere-1ajj

### Banana
- Banana V2.1 Infra (VM isolation): https://www.banana.dev/blog/banana-infra-v2-1
- Banana Sunset Announcement: https://www.banana.dev/blog/sunset
- Banana Serverless GPUs: https://www.banana.dev/blog/serverless-gpus-inference-hosting
- HN Discussion of Sunset: https://news.ycombinator.com/item?id=39288915
- Thinkpeak Banana Analysis: https://thinkpeak.ai/banana-serverless-gpu-pricing-2026/
- Railway Blog: https://blog.railway.com/p/serverless-inference-gpu-banana-dev

### Decentralized (Akash, Golem, Spheron)
- Akash Provider Architecture: https://akash.network/docs/providers/architecture/overview/
- Akash Confidential Compute (AEP-83): https://akash.network/roadmap/aep-83/
- Akash AEP-65: https://akash.network/roadmap/aep-65/
- Akash Hardware Verification (AEP-29): https://akash.network/roadmap/aep-29/
- Akash Private Overlay Networking (AEP-48): https://akash.network/roadmap/aep-48/
- Akash Providers & Leases: https://akash.network/docs/learn/core-concepts/providers-leases/
- Akash 2025 Review: https://akash.network/blog/akash-2025-year-in-review/
- Akash State of Q1 2025 (Messari): https://messari.io/report/state-of-akash-q1-2025
- Akash TEE Support (GitHub): https://github.com/akash-network/support/issues/329
- Golem-Workers API: https://blog.golem.network/golem-workers/
- Golem Compute Lifecycle: https://blog.golem.network/an-overview-of-a-computations-lifecycle-in-golem/
- Golem Graphene-ng SGX: https://medium.com/golem-project/introducing-graphene-ng-running-arbitrary-payloads-in-sgx-enclaves-a03f219447a5
- Golem x Salad Partnership: https://news.bitcoin.com/salad-com-and-golem-network-partner-to-pilot-decentralized-gpu-cloud-infrastructure/
- Golem Concepts: https://learn.golem.cloud/concepts
- Golem-Workers Create Node: https://docs.golem.network/docs/creators/golem-workers/create-node
- Spheron NVIDIA Confidential Computing: https://blog.spheron.network/maximize-security-using-nvidia-confidential-computing
- Spheron EU AI Act Compliance: https://www.spheron.network/blog/eu-ai-act-compliance-gpu-cloud-guide-2026/
- Spheron Product Roadmap: https://foundation.spheron.network/knowledge-gallery/roadmap-2025
- Spheron vs AWS/GCP/Azure: https://www.spheron.network/blog/aws-gcp-azure-gpu-alternative/
- Spheron x Nexus Partnership: https://blog.nexus.xyz/partnering-with-spheron-on-scaling-verifiable-compute-with-the-worlds-largest-community-powered-data-center/
- Spheron NEBULA Phase: https://blog.spheron.network/nebula-phase-launches-the-new-era-of-decentralized-compute-has-begun
- Spheron Alea Research: https://alearesearch.io/perspectives/spheron/
- NVIDIA GPU CC Demystified (arXiv): https://arxiv.org/pdf/2507.02770v1

### General / Cross-Provider
- DevZero Multi-Tenant GPU Security: https://www.devzero.io/blog/gpu-multi-tenancy
- Inrol Multi-Tenant GPU Security: https://introl.com/blog/multi-tenant-gpu-security-isolation-strategies-shared-infrastructure-2025
- NVIDIA GPU CC Demystified: https://arxiv.org/pdf/2507.02770v1
- AI Data Residency Patterns (Digital Applied): https://www.digitalapplied.com/blog/ai-data-residency-architecture-patterns-2026
- Europe Data Center Portfolio Report 2026: https://menafn.com/1110846857/Europe-Colocation-Data-Center-Portfolio-Report-And-Database-2026
- Europe Data Center Map 2026: https://www.thenextgentechinsider.com/posts/ai-surge-and-policy-shifts-redraw-europes-data-center-map-by-2026
- DeployBase SOC 2 GPU Cloud: https://deploybase.ai/articles/best-gpu-cloud-with-soc-2-compliance

---

## 5. Key Takeaways

### Tier 1 - Enterprise-Ready with Full Compliance & EU Presence
**CoreWeave** leads on every axis: bare metal with DPU-enforced isolation, SOC 2 + ISO 27001 + ISO 27017/27018 + HIPAA, multi-region EU data centres (UK, Sweden, Norway, Spain), NVIDIA CC for GPU TEE, full VPC/SSO/SIEM. **Fireworks AI** uniquely holds ISO 42001 (AI Management), plus SOC 2, ISO 27001/27701, HIPAA, and BYOC/airgapped for maximum customer control. **Lambda Labs** is strong on certs (SOC 2, ISO 27001, PCI DSS Level 1, HIPAA, HITRUST) but weak on EU data centres.

### Tier 2 - Growing Compliance with Some Gaps
**Together AI** (SOC 2 Type II, HIPAA, expanding EU presence in Sweden), **RunPod** (SOC 2 Type II, HIPAA, GDPR, wide EU data centre coverage but no VPC peering), **Modal** (SOC 2 Type II, HIPAA, gVisor sandbox), **Beam** (SOC 2 Type II, open-source runtime, gVisor).

### Tier 3 - Limited Compliance; Best for Dev/Experimental
**Vast.ai** (SOC 2 Type II but marketplace model limits enterprise assurance), **Replicate** (SOC 2 self-attested, US-only, no ISO/HIPAA - best for prototyping), **Akash/Golem/Spheron** (decentralized - no platform-level compliance, though Spheron partners with certified data centres).

### Key Gaps Identified
1. **ISO 42001 (AI Management)** - Only Fireworks AI has achieved this. CoreWeave is in progress. No other provider pursues it.
2. **GPU TEE (Confidential Computing)** - CoreWeave (NVIDIA CC on H100+), Spheron (NVIDIA CC), Akash (roadmap). Others do not offer GPU TEE.
3. **EU Data Sovereignty** - CoreWeave dominates with 8+ EU AZs. Together AI expanding. Lambda and Replicate are US-centric.
4. **Agent-Specific Infrastructure** - None of the providers offer agent-specific security primitives (e.g., agent identity, agent sandboxing, inter-agent policies). Modal and Beam's gVisor sandboxes are the closest approximation for running untrusted agent code.
5. **Safety Filters / Content Moderation** - Only Fireworks AI (via ISO 42001) and Together AI (opt-in ZDR) offer structured approaches. Replicate has none. No provider offers a programmable safety filter API for agentic workloads.

### Strategic Recommendations
- For **enterprise agent deployments in EU**: CoreWeave (compute) + Fireworks AI (inference with BYOC) is the strongest stack.
- For **serverless agent workloads**: Modal (gVisor sandbox, SOC 2, HIPAA) or Beam (open-source, self-hostable).
- For **cost-sensitive non-regulated workloads**: RunPod or Vast.ai.
- For **decentralized/anti-censorship**: Akash (most mature with TEE roadmap) or Spheron (largest GPU pool).
- **Replicate** is not recommended for production EU workloads or regulated industries.
