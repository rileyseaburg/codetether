import { Container } from '@/components/Container'
import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'Terms of Service - A2A Server MCP',
    description: 'Terms of Service for A2A Server MCP and Quantum Forge',
}

// Force static generation at build time
export const dynamic = 'force-static'

export default function TermsOfService() {
    return (
        <div className="py-24 sm:py-32">
            <Container>
                <div className="mx-auto max-w-3xl">
                    <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
                        Terms of Service
                    </h1>
                    <p className="mt-6 text-lg text-gray-500">
                        Last updated: January 15, 2026
                    </p>

                    <div className="mt-12 prose prose-gray max-w-none">
                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">1. Agreement to Terms</h2>
                        <p className="mt-4 text-gray-600">
                            By accessing or using A2A Server MCP (&quot;Service&quot;), you agree to be bound by these Terms
                            of Service (&quot;Terms&quot;). If you disagree with any part of these terms, you may not
                            access the Service.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">2. Description of Service</h2>
                        <p className="mt-4 text-gray-600">
                            A2A Server MCP is an agent-to-agent communication platform that enables AI agents to
                            communicate with each other using the Model Context Protocol (MCP) and Google&apos;s
                            Agent-to-Agent (A2A) specification. The Service includes:
                        </p>
                        <ul className="mt-4 space-y-2 text-gray-600">
                            <li>• Open-source software for self-hosting</li>
                            <li>• Managed cloud hosting (Pro tier)</li>
                            <li>• Enterprise deployment and support services</li>
                        </ul>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">3. Open Source License</h2>
                        <p className="mt-4 text-gray-600">
                            A2A Server MCP is licensed under the Apache License 2.0. You may use, modify, and
                            distribute the software in accordance with this license. The open-source license
                            applies to the software itself, not to the managed services we provide.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">4. Account Registration</h2>
                        <p className="mt-4 text-gray-600">
                            To access certain features of the Service, you must register for an account. You agree to:
                        </p>
                        <ul className="mt-4 space-y-2 text-gray-600">
                            <li>• Provide accurate, current, and complete information</li>
                            <li>• Maintain and update your account information</li>
                            <li>• Maintain the security of your account credentials</li>
                            <li>• Accept responsibility for all activities under your account</li>
                            <li>• Notify us immediately of any unauthorized access</li>
                        </ul>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">5. Acceptable Use</h2>
                        <p className="mt-4 text-gray-600">
                            You agree not to use the Service to:
                        </p>
                        <ul className="mt-4 space-y-2 text-gray-600">
                            <li>• Violate any applicable laws or regulations</li>
                            <li>• Transmit malicious code or conduct security attacks</li>
                            <li>• Interfere with or disrupt the Service or servers</li>
                            <li>• Attempt to gain unauthorized access to any systems</li>
                            <li>• Send spam or unsolicited communications</li>
                            <li>• Infringe on intellectual property rights</li>
                            <li>• Engage in activities that are harmful, threatening, or abusive</li>
                        </ul>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">6. Subscription and Payment</h2>

                        <h3 className="text-xl font-semibold text-gray-900 mt-8">Free Tier</h3>
                        <p className="mt-4 text-gray-600">
                            The open-source version is free to use under the Apache License 2.0.
                        </p>

                        <h3 className="text-xl font-semibold text-gray-900 mt-8">Paid Tiers</h3>
                        <p className="mt-4 text-gray-600">
                            Pro and Enterprise subscriptions are billed monthly or annually. Payments are
                            processed by Stripe. You authorize us to charge your payment method for all
                            applicable fees.
                        </p>

                        <h3 className="text-xl font-semibold text-gray-900 mt-8">Refunds</h3>
                        <p className="mt-4 text-gray-600">
                            Annual subscriptions include a 30-day money-back guarantee. Monthly subscriptions
                            are non-refundable but may be cancelled at any time.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">7. Service Level Agreement</h2>
                        <p className="mt-4 text-gray-600">
                            Pro and Enterprise tiers include a 99.9% uptime SLA. Service credits will be
                            provided for downtime exceeding this threshold. See our SLA documentation for
                            details.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">8. Intellectual Property</h2>
                        <p className="mt-4 text-gray-600">
                            The A2A Server MCP name, logo, and branding are trademarks of Quantum Forge. The
                            Service and its original content (excluding user content) are protected by
                            copyright, trademark, and other intellectual property laws.
                        </p>
                        <p className="mt-4 text-gray-600">
                            You retain ownership of any content you submit through the Service. By submitting
                            content, you grant us a license to use it solely for providing the Service.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">9. Data and Privacy</h2>
                        <p className="mt-4 text-gray-600">
                            Your use of the Service is also governed by our Privacy Policy. By using the
                            Service, you consent to our data practices as described in the Privacy Policy.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">10. Limitation of Liability</h2>
                        <p className="mt-4 text-gray-600">
                            TO THE MAXIMUM EXTENT PERMITTED BY LAW, QUANTUM FORGE SHALL NOT BE LIABLE FOR ANY
                            INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF
                            PROFITS OR REVENUES, WHETHER INCURRED DIRECTLY OR INDIRECTLY.
                        </p>
                        <p className="mt-4 text-gray-600">
                            OUR TOTAL LIABILITY FOR ANY CLAIMS UNDER THESE TERMS SHALL NOT EXCEED THE AMOUNT
                            YOU PAID US IN THE PAST TWELVE MONTHS.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">11. Disclaimer of Warranties</h2>
                        <p className="mt-4 text-gray-600">
                            THE SERVICE IS PROVIDED &quot;AS IS&quot; AND &quot;AS AVAILABLE&quot; WITHOUT WARRANTIES OF ANY KIND,
                            EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF
                            MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">12. Indemnification</h2>
                        <p className="mt-4 text-gray-600">
                            You agree to indemnify, defend, and hold harmless Quantum Forge and its officers,
                            directors, employees, and agents from any claims, damages, losses, liabilities, and
                            expenses arising from your use of the Service or violation of these Terms.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">13. Termination</h2>
                        <p className="mt-4 text-gray-600">
                            We may terminate or suspend your access to the Service immediately, without prior
                            notice, for any reason, including breach of these Terms. Upon termination, your
                            right to use the Service will cease immediately.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">14. Governing Law</h2>
                        <p className="mt-4 text-gray-600">
                            These Terms shall be governed by and construed in accordance with the laws of the
                            State of Delaware, without regard to its conflict of law provisions.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">15. Dispute Resolution</h2>
                        <p className="mt-4 text-gray-600">
                            Any disputes arising out of or relating to these Terms or the Service shall be
                            resolved through binding arbitration in accordance with the rules of the American
                            Arbitration Association.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">16. Changes to Terms</h2>
                        <p className="mt-4 text-gray-600">
                            We reserve the right to modify these Terms at any time. We will provide notice of
                            material changes via email or prominent notice on our website. Continued use of
                            the Service after such modifications constitutes acceptance of the updated Terms.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">17. Contact Us</h2>
                        <p className="mt-4 text-gray-600">
                            For questions about these Terms:
                        </p>
                        <ul className="mt-4 space-y-2 text-gray-600">
                            <li>• Email: legal@quantum-forge.net</li>
                            <li>• GitHub: github.com/rileyseaburg/codetether/issues</li>
                        </ul>
                    </div>
                </div>
            </Container>
        </div>
    )
}
