# CodeTether Security Architecture

**The Secure Agent Runtime: Zero Trust Orchestration for Regulated Enterprises**

**Classification:** PUBLIC / TECHNICAL
**Audience:** Enterprise Security Operations (SecOps), GRC, and Network Architecture Teams
**Date:** December 2025

---

## 1. Executive Summary

The rapid adoption of "Agentic AI" in the enterprise has historically been blocked by a fundamental security paradox: to be useful, agents need access to internal data; to be secure, internal data must not be exposed to external cloud providers.

CodeTether resolves this conflict through **Inversion of Control**.

Unlike traditional SaaS integration models that require opening inbound firewall ports or establishing persistent VPN tunnels, CodeTether utilizes a **Distributed Worker Architecture**. We do not ask you to send your data to our cloud. Instead, you deploy our ephemeral runtime—the **CodeTether Worker**—inside your secure perimeter.

This architecture ensures that CodeTether operates with the same security profile as a standard CI/CD runner (e.g., Jenkins or GitHub Actions). It requires **zero inbound ports**, maintains strict data residency via "Data Gravity," and provides immutable audit trails for every agent action.

---

## 2. The Architecture of Trust: Control Plane vs. Data Plane

CodeTether enforces a strict logical and physical separation between the **Control Plane** (managed by CodeTether SaaS) and the **Data Plane** (managed by the Customer). This separation creates a "Logic Air Gap."

### 2.1 The Control Plane (SaaS)

Hosted in our SOC 2 Type II compliant environment, the Control Plane is responsible for orchestration only:

- **Signal Routing:** Managing the queue of abstract tasks (e.g., "Run Q3 Analysis").
- **Identity Provider:** Centralized OIDC authentication via Keycloak.
- **Telemetry:** Aggregating *metadata* (task status, timestamps, success/failure rates).

**Security Guarantee:** The Control Plane does not store, process, or see your source code, database records, or PII.

### 2.2 The Data Plane (Customer VPC)

The **Agent Worker** runs as a containerized workload (Docker/Kubernetes) within your secure VPC. It is responsible for:

- **Execution:** Running the actual logic (SQL queries, code analysis, file manipulation).
- **Tool Access:** Interfacing with internal APIs via the Model Context Protocol (MCP).
- **Data Residency:** Ensuring sensitive data never traverses the public internet.

**Impact:** Even if the CodeTether Control Plane were fully compromised, the attacker would have **no access** to your database credentials or source code, as these secrets reside solely in your local Kubernetes secrets and never leave your environment.

---

## 3. Network Security: The "Reverse-Polling" Mechanism

The primary objection to external integrations is the "Firewall Objection"—the risk associated with opening inbound ports. CodeTether eliminates this risk entirely.

### 3.1 Outbound-Only Architecture

The Agent Worker utilizes a **Pull-Based (Polling)** communication model.

- **No Inbound Ports:** There are no open listening ports on the Worker. It rejects all unsolicited inbound traffic.
- **Protocol:** Communication is established via outbound HTTPS (TCP/443) only.
- **Mechanism:** The Worker utilizes Server-Sent Events (SSE) and long-polling to ask the Control Plane: *"Are there tasks for me?"*
- **Encryption:** All traffic is encapsulated in **TLS 1.3** (utilizing strong cipher suites and prohibiting legacy SSL versions).

### 3.2 Firewall Configuration

To deploy CodeTether, your firewall rules require a single allow-list entry:

| Direction | Destination | Port | Protocol |
|-----------|-------------|------|----------|
| Outbound | `api.codetether.run` | 443 | HTTPS |

Because the connection is initiated from *inside* the trusted network, no Site-to-Site VPNs, Bastion hosts, or DMZ exceptions are required.

---

## 4. Data Residency & Privacy: The "Data Gravity" Principle

Regulated industries cannot afford to stream proprietary code or customer PII to an external vendor. CodeTether adheres to strict **Data Gravity** principles: logic moves to the data; data does not move to the logic.

### 4.1 Local Processing

When a task is assigned, the source code and database rows are processed entirely within the Agent Worker container in your VPC.

- **Streaming Metadata:** The Worker streams the *status* ("Running tests...", "Syntax error found") back to the Control Plane.
- **Sanitized Output:** Actual data payloads are processed locally. Only the result (e.g., "Revenue calculated: $50k" or a sanitized summary) is transmitted back to the central dashboard.

### 4.2 Prevention of Leakage

If using external LLMs, the Worker acts as a proxy with **Pre-Flight Redaction**. It can be configured to scrub sensitive entities (Credit Card numbers, SSNs) via regex/NLP filters locally *before* any context is sent to the inference API.

---

## 5. Identity & Governance: RBAC & MCP

In a Zero Trust architecture, identity is the new perimeter. CodeTether leverages **Keycloak** for enterprise-grade Identity and Access Management (IAM).

### 5.1 Fine-Grained RBAC

We treat Agents as non-human identities with strict permissions.

- **Identity Separation:** A "Test Agent" is cryptographically distinct from a "Deploy Agent."
- **Role Scoping:** Access is granted via fine-grained RBAC. *Example: The 'Test Agent' can read the DB, but only the 'Deploy Agent' can write to it.*

### 5.2 The Model Context Protocol (MCP) as a Policy Layer

We utilize the **Model Context Protocol (MCP)** to standardize how Agents access your internal tools. This allows security teams to wrap **"Policy Layers"** around tool access.

- **Scenario:** An agent wants to run a SQL query.
- **Policy Enforcement:** The MCP server on the Worker can enforce a "Read-Only" policy. If the agent attempts a `DROP TABLE` command, the MCP layer blocks the execution locally. The command never reaches the database.

### 5.3 Immutable Audit Logging

Every action is logged in an immutable session history, exportable to your SIEM (Splunk, Datadog):

| Field | Description |
|-------|-------------|
| **Who** | User ID (or Parent Agent ID) |
| **What** | The specific MCP tool called |
| **When** | UTC Timestamp |
| **Why** | The prompt context that triggered the action |

---

## 6. Supply Chain Security

To ensure the integrity of the software running inside your perimeter:

- **Signed Images:** All Docker images are cryptographically signed. You can verify signatures via admission controllers before the container starts.
- **Minimal Base Images:** We use distroless or minimal Alpine bases to reduce the attack surface.
- **SBOM:** A Software Bill of Materials (SBOM) is available for every release, detailing all open-source dependencies and their versions.

---

## 7. Compliance Frameworks

CodeTether's architecture supports compliance with major regulatory frameworks:

| Framework | How CodeTether Supports Compliance |
|-----------|-----------------------------------|
| **HIPAA** | PHI stays in your VPC. BAA available for enterprise customers. |
| **SOC 2 Type II** | Control Plane maintains SOC 2 certification. Audit logs exportable. |
| **PCI-DSS** | Cardholder data never leaves your network. Network segmentation supported. |
| **FedRAMP** | Self-hosted deployment supports FedRAMP requirements. Air-gap compatible. |
| **GDPR** | Data residency maintained. No cross-border data transfer required. |

---

## 8. Conclusion

CodeTether transforms the AI Agent from a "Black Box" security risk into a managed, observable, and policy-governed IT asset. By decoupling the Control Plane from the Execution Plane, we allow regulated enterprises to innovate with AI agents without compromising their security posture.

---

## Contact

**Security Team:** security@codetether.run
**Sales:** sales@codetether.run
**Documentation:** https://docs.codetether.run

---

*© 2025 CodeTether. All rights reserved.*

*This document is provided for informational purposes and does not constitute legal advice. Consult with your security and compliance teams for specific guidance.*
