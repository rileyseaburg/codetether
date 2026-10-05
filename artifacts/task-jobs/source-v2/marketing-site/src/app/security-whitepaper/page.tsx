'use client'

import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

function ShieldIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
    )
}

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
    )
}

function LockIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
    )
}

export default function SecurityWhitepaper() {
    return (
        <main className="bg-white dark:bg-gray-950">
            {/* Hero */}
            <section className="relative overflow-hidden bg-gradient-to-b from-cyan-600 to-cyan-800 dark:from-cyan-700 dark:to-cyan-900 py-20 sm:py-32">
                <div className="absolute inset-0 opacity-10">
                    <svg className="h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                        <defs>
                            <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
                                <path d="M 10 0 L 0 0 0 10" fill="none" stroke="white" strokeWidth="0.5" />
                            </pattern>
                        </defs>
                        <rect width="100" height="100" fill="url(#grid)" />
                    </svg>
                </div>
                <Container className="relative">
                    <div className="mx-auto max-w-3xl text-center">
                        <div className="flex justify-center mb-6">
                            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/20 backdrop-blur">
                                <ShieldIcon className="h-8 w-8 text-white" />
                            </div>
                        </div>
                        <p className="text-sm font-semibold text-cyan-200 uppercase tracking-wide mb-4">
                            Security Architecture Whitepaper
                        </p>
                        <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
                            The Secure Agent Runtime
                        </h1>
                        <p className="mt-4 text-xl text-cyan-100">
                            Zero Trust Orchestration for Regulated Enterprises
                        </p>
                        <p className="mt-6 text-lg text-cyan-200">
                            Classification: PUBLIC / TECHNICAL
                        </p>
                        <p className="mt-2 text-sm text-cyan-300">
                            Audience: Enterprise Security Operations (SecOps), GRC, and Network Architecture Teams
                        </p>
                    </div>
                </Container>
            </section>

            {/* Executive Summary */}
            <section className="py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            1. Executive Summary
                        </h2>
                        <div className="mt-6 space-y-4 text-lg text-gray-600 dark:text-gray-300">
                            <p>
                                The rapid adoption of &ldquo;Agentic AI&rdquo; in the enterprise has historically been blocked by a fundamental security paradox: to be useful, agents need access to internal data; to be secure, internal data must not be exposed to external cloud providers.
                            </p>
                            <p>
                                CodeTether resolves this conflict through <strong className="text-cyan-600 dark:text-cyan-400">Inversion of Control</strong>.
                            </p>
                            <p>
                                Unlike traditional SaaS integration models that require opening inbound firewall ports or establishing persistent VPN tunnels, CodeTether utilizes a <strong>Distributed Worker Architecture</strong>. We do not ask you to send your data to our cloud. Instead, you deploy our ephemeral runtime—the <strong>CodeTether Worker</strong>—inside your secure perimeter.
                            </p>
                            <div className="rounded-xl bg-cyan-50 dark:bg-cyan-900/20 border border-cyan-200 dark:border-cyan-800 p-6 mt-6">
                                <p className="text-cyan-800 dark:text-cyan-300 font-medium">
                                    This architecture ensures that CodeTether operates with the same security profile as a standard CI/CD runner (e.g., Jenkins or GitHub Actions). It requires <strong>zero inbound ports</strong>, maintains strict data residency via &ldquo;Data Gravity,&rdquo; and provides immutable audit trails for every agent action.
                                </p>
                            </div>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Control Plane vs Data Plane */}
            <section className="py-16 sm:py-24 bg-gray-50 dark:bg-gray-900">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            2. The Architecture of Trust
                        </h2>
                        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                            CodeTether enforces a strict logical and physical separation between the <strong>Control Plane</strong> (managed by CodeTether SaaS) and the <strong>Data Plane</strong> (managed by the Customer). This separation creates a &ldquo;Logic Air Gap.&rdquo;
                        </p>

                        <div className="mt-10 grid gap-8 md:grid-cols-2">
                            {/* Control Plane */}
                            <div className="rounded-2xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-6">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/30">
                                        <span className="text-xl">☁️</span>
                                    </div>
                                    <h3 className="font-semibold text-gray-900 dark:text-white">Control Plane (SaaS)</h3>
                                </div>
                                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                                    Hosted in our SOC 2 Type II compliant environment
                                </p>
                                <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
                                    <li className="flex items-start gap-2">
                                        <CheckIcon className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                                        <span><strong>Signal Routing:</strong> Managing the queue of abstract tasks</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <CheckIcon className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                                        <span><strong>Identity Provider:</strong> Centralized OIDC via Keycloak</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <CheckIcon className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                                        <span><strong>Telemetry:</strong> Aggregating metadata only</span>
                                    </li>
                                </ul>
                                <div className="mt-4 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                                    <p className="text-xs text-blue-700 dark:text-blue-300">
                                        <strong>Security Guarantee:</strong> The Control Plane is not in the inference data path and is designed to operate on metadata (task state, routing, audit events) rather than prompt payloads.
                                    </p>
                                </div>
                            </div>

                            {/* Data Plane */}
                            <div className="rounded-2xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-6">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900/30">
                                        <span className="text-xl">🏢</span>
                                    </div>
                                    <h3 className="font-semibold text-gray-900 dark:text-white">Data Plane (Customer VPC)</h3>
                                </div>
                                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                                    Runs within your secure VPC as a containerized workload
                                </p>
                                <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
                                    <li className="flex items-start gap-2">
                                        <CheckIcon className="h-4 w-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                                        <span><strong>Execution:</strong> Running actual logic locally</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <CheckIcon className="h-4 w-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                                        <span><strong>Tool Access:</strong> Interfacing via MCP</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <CheckIcon className="h-4 w-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                                        <span><strong>Data Handling:</strong> Sensitive payloads are handled on the Worker; optional model calls go directly to your approved model tenant using your keys</span>
                                    </li>
                                </ul>
                                <div className="mt-4 p-3 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800">
                                    <p className="text-xs text-emerald-700 dark:text-emerald-300">
                                        <strong>Impact:</strong> Even if the Control Plane were fully compromised, attackers would have no access to your credentials or source code.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Network Security */}
            <section className="py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            3. Network Security: Reverse-Polling
                        </h2>
                        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                            The primary objection to external integrations is the &ldquo;Firewall Objection&rdquo;—the risk associated with opening inbound ports. CodeTether eliminates this risk entirely.
                        </p>

                        <div className="mt-10 rounded-2xl bg-gray-900 p-6 sm:p-8">
                            <h3 className="text-xl font-semibold text-white mb-6">Outbound-Only Architecture</h3>
                            <div className="grid gap-4 sm:grid-cols-2">
                                <div className="flex items-start gap-3">
                                    <CheckIcon className="h-5 w-5 text-emerald-400 mt-0.5 flex-shrink-0" />
                                    <div>
                                        <p className="font-medium text-white">No Inbound Ports</p>
                                        <p className="text-sm text-gray-400">Worker rejects all unsolicited inbound traffic</p>
                                    </div>
                                </div>
                                <div className="flex items-start gap-3">
                                    <CheckIcon className="h-5 w-5 text-emerald-400 mt-0.5 flex-shrink-0" />
                                    <div>
                                        <p className="font-medium text-white">HTTPS Only (TCP/443)</p>
                                        <p className="text-sm text-gray-400">Standard outbound traffic pattern</p>
                                    </div>
                                </div>
                                <div className="flex items-start gap-3">
                                    <CheckIcon className="h-5 w-5 text-emerald-400 mt-0.5 flex-shrink-0" />
                                    <div>
                                        <p className="font-medium text-white">SSE & Long-Polling</p>
                                        <p className="text-sm text-gray-400">Worker asks: &ldquo;Are there tasks for me?&rdquo;</p>
                                    </div>
                                </div>
                                <div className="flex items-start gap-3">
                                    <CheckIcon className="h-5 w-5 text-emerald-400 mt-0.5 flex-shrink-0" />
                                    <div>
                                        <p className="font-medium text-white">TLS 1.3 Encryption</p>
                                        <p className="text-sm text-gray-400">Strong cipher suites, no legacy SSL</p>
                                    </div>
                                </div>
                            </div>

                            <div className="mt-8 border-t border-gray-700 pt-6">
                                <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">Firewall Configuration</h4>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-left text-gray-400">
                                                <th className="pb-2">Direction</th>
                                                <th className="pb-2">Destination</th>
                                                <th className="pb-2">Port</th>
                                                <th className="pb-2">Protocol</th>
                                            </tr>
                                        </thead>
                                        <tbody className="text-white">
                                            <tr>
                                                <td className="py-2 text-emerald-400">Outbound</td>
                                                <td className="py-2 font-mono text-cyan-400">api.codetether.run</td>
                                                <td className="py-2">443</td>
                                                <td className="py-2">HTTPS</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                                <p className="mt-4 text-sm text-gray-400">
                                    No Site-to-Site VPNs, Bastion hosts, or DMZ exceptions required.
                                </p>
                            </div>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Data Gravity */}
            <section className="py-16 sm:py-24 bg-gray-50 dark:bg-gray-900">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            4. Data Residency: The &ldquo;Data Gravity&rdquo; Principle
                        </h2>
                        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                            Regulated industries cannot afford to stream proprietary code or customer PII to an external vendor. CodeTether adheres to strict Data Gravity principles: <strong className="text-cyan-600 dark:text-cyan-400">logic moves to the data; data does not move to the logic</strong>.
                        </p>

                        <div className="mt-10 grid gap-6 sm:grid-cols-2">
                            <div className="rounded-xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-6">
                                <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Local Processing</h3>
                                <ul className="space-y-3 text-sm text-gray-600 dark:text-gray-300">
                                    <li className="flex items-start gap-2">
                                        <span className="text-cyan-500">→</span>
                                        <span>Tools and sensitive context run on Workers inside your environment</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <span className="text-cyan-500">→</span>
                                        <span>Only <em>metadata</em> is required by the Control Plane (status, routing, audit events)</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <span className="text-cyan-500">→</span>
                                        <span>Optional centralized logs are configurable; you decide what is retained and where</span>
                                    </li>
                                </ul>
                            </div>
                            <div className="rounded-xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-6">
                                <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Pre-Flight Redaction</h3>
                                <ul className="space-y-3 text-sm text-gray-600 dark:text-gray-300">
                                    <li className="flex items-start gap-2">
                                        <span className="text-cyan-500">→</span>
                                        <span>Worker acts as the policy enforcement point before any external inference call</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <span className="text-cyan-500">→</span>
                                        <span>Regex/NLP filters scrub sensitive entities</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <span className="text-cyan-500">→</span>
                                        <span>PII redacted <em>before</em> direct-to-tenant inference API calls (e.g., Azure OpenAI)</span>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Identity & Governance */}
            <section className="py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            5. Identity & Governance: RBAC & MCP
                        </h2>
                        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                            In a Zero Trust architecture, identity is the new perimeter. CodeTether leverages <strong>Keycloak</strong> for enterprise-grade Identity and Access Management (IAM).
                        </p>

                        <div className="mt-10 space-y-8">
                            {/* RBAC */}
                            <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-6">
                                <div className="flex items-center gap-3 mb-4">
                                    <LockIcon className="h-6 w-6 text-cyan-500" />
                                    <h3 className="font-semibold text-gray-900 dark:text-white">Fine-Grained RBAC</h3>
                                </div>
                                <p className="text-gray-600 dark:text-gray-300 mb-4">
                                    We treat Agents as non-human identities with strict permissions.
                                </p>
                                <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
                                    <li className="flex items-start gap-2">
                                        <CheckIcon className="h-4 w-4 text-cyan-500 mt-0.5" />
                                        <span><strong>Identity Separation:</strong> A &ldquo;Test Agent&rdquo; is cryptographically distinct from a &ldquo;Deploy Agent&rdquo;</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <CheckIcon className="h-4 w-4 text-cyan-500 mt-0.5" />
                                        <span><strong>Role Scoping:</strong> Test Agent can read DB; only Deploy Agent can write</span>
                                    </li>
                                </ul>
                            </div>

                            {/* MCP Policy */}
                            <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-6">
                                <div className="flex items-center gap-3 mb-4">
                                    <ShieldIcon className="h-6 w-6 text-cyan-500" />
                                    <h3 className="font-semibold text-gray-900 dark:text-white">MCP as a Policy Layer</h3>
                                </div>
                                <p className="text-gray-600 dark:text-gray-300 mb-4">
                                    The Model Context Protocol allows security teams to wrap <strong>&ldquo;Policy Layers&rdquo;</strong> around tool access.
                                </p>
                                <div className="rounded-lg bg-gray-100 dark:bg-gray-800 p-4">
                                    <p className="text-sm text-gray-700 dark:text-gray-300">
                                        <strong>Scenario:</strong> An agent wants to run a SQL query.<br />
                                        <strong>Policy Enforcement:</strong> The MCP server enforces &ldquo;Read-Only&rdquo; policy. If the agent attempts a <code className="bg-gray-200 dark:bg-gray-700 px-1 rounded">DROP TABLE</code> command, the MCP layer blocks it locally. The command never reaches the database.
                                    </p>
                                </div>
                            </div>

                            {/* Audit Logging */}
                            <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-6">
                                <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Immutable Audit Logging</h3>
                                <p className="text-gray-600 dark:text-gray-300 mb-4">
                                    Every action is logged and exportable to your SIEM (Splunk, Datadog):
                                </p>
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div className="flex items-center gap-2">
                                        <span className="font-semibold text-gray-900 dark:text-white">Who:</span>
                                        <span className="text-gray-600 dark:text-gray-300">User ID / Agent ID</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="font-semibold text-gray-900 dark:text-white">What:</span>
                                        <span className="text-gray-600 dark:text-gray-300">MCP tool called</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="font-semibold text-gray-900 dark:text-white">When:</span>
                                        <span className="text-gray-600 dark:text-gray-300">UTC Timestamp</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="font-semibold text-gray-900 dark:text-white">Why:</span>
                                        <span className="text-gray-600 dark:text-gray-300">Prompt context</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Supply Chain & Compliance */}
            <section className="py-16 sm:py-24 bg-gray-50 dark:bg-gray-900">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            6. Supply Chain Security
                        </h2>
                        <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                            To ensure the integrity of software running inside your perimeter:
                        </p>

                        <div className="mt-8 grid gap-4 sm:grid-cols-3">
                            <div className="rounded-xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-5">
                                <div className="text-2xl mb-2">🔏</div>
                                <h3 className="font-semibold text-gray-900 dark:text-white">Signed Images</h3>
                                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                    All Docker images cryptographically signed. Verify via admission controllers.
                                </p>
                            </div>
                            <div className="rounded-xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-5">
                                <div className="text-2xl mb-2">📦</div>
                                <h3 className="font-semibold text-gray-900 dark:text-white">Minimal Base</h3>
                                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                    Distroless or minimal Alpine bases to reduce attack surface.
                                </p>
                            </div>
                            <div className="rounded-xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-5">
                                <div className="text-2xl mb-2">📋</div>
                                <h3 className="font-semibold text-gray-900 dark:text-white">SBOM Available</h3>
                                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                    Software Bill of Materials for every release with all dependencies.
                                </p>
                            </div>
                        </div>

                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white mt-16">
                            7. Compliance Frameworks
                        </h2>

                        <div className="mt-8 grid gap-4 sm:grid-cols-2">
                            {[
                                { icon: '🏥', name: 'HIPAA', desc: 'PHI stays in your VPC. BAA available.' },
                                { icon: '🔒', name: 'SOC 2 Type II', desc: 'Control Plane maintains certification.' },
                                { icon: '💳', name: 'PCI-DSS', desc: 'Cardholder data stays under your control; enforce egress policy at the Worker.' },
                                { icon: '🏛️', name: 'FedRAMP', desc: 'Self-hosted, air-gap compatible.' },
                            ].map((item) => (
                                <div key={item.name} className="rounded-xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-5 flex items-start gap-4">
                                    <div className="text-2xl">{item.icon}</div>
                                    <div>
                                        <h3 className="font-semibold text-gray-900 dark:text-white">{item.name}</h3>
                                        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{item.desc}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </Container>
            </section>

            {/* Conclusion */}
            <section className="py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-3xl">
                        <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                            8. Conclusion
                        </h2>
                        <p className="mt-6 text-lg text-gray-600 dark:text-gray-300">
                            CodeTether transforms the AI Agent from a &ldquo;Black Box&rdquo; security risk into a managed, observable, and policy-governed IT asset. By decoupling the Control Plane from the Execution Plane, we allow regulated enterprises to innovate with AI agents without compromising their security posture.
                        </p>

                        <div className="mt-10 rounded-2xl bg-gradient-to-r from-cyan-600 to-cyan-800 p-8 text-white">
                            <h3 className="text-xl font-bold mb-4">The &ldquo;Runner&rdquo; Analogy</h3>
                            <p className="text-cyan-100">
                                &ldquo;It works exactly like a GitHub Action runner. It sits in your VPC, polls for work on port 443, does the work locally, and reports the status. No inbound ports.&rdquo;
                            </p>
                        </div>
                    </div>
                </Container>
            </section>

            {/* CTA */}
            <section className="py-16 sm:py-24 bg-gradient-to-r from-cyan-600 to-cyan-800 dark:from-cyan-700 dark:to-cyan-900">
                <Container>
                    <div className="mx-auto max-w-2xl text-center">
                        <h2 className="text-3xl font-bold tracking-tight text-white">
                            Ready to Secure Your AI Workflows?
                        </h2>
                        <p className="mt-4 text-lg text-cyan-100">
                            Schedule a Security Architecture Review with our team.
                        </p>
                        <div className="mt-8 flex flex-wrap justify-center gap-4">
                            <Button href="/#contact" className="!bg-white !text-cyan-700 hover:!bg-cyan-50">
                                Request Security Review
                            </Button>
                            <Button href="/security-whitepaper.md" variant="outline" className="!border-white/50 !text-white hover:!bg-white/10">
                                Download Markdown
                            </Button>
                        </div>
                    </div>
                </Container>
            </section>
        </main>
    )
}
