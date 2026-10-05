import { Container } from '@/components/Container'
import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'Privacy Policy - A2A Server MCP',
    description: 'Privacy Policy for A2A Server MCP and Quantum Forge',
}

// Force static generation at build time
export const dynamic = 'force-static'

export default function PrivacyPolicy() {
    return (
        <div className="py-24 sm:py-32">
            <Container>
                <div className="mx-auto max-w-3xl">
                    <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
                        Privacy Policy
                    </h1>
                    <p className="mt-6 text-lg text-gray-500">
                        Last updated: January 15, 2026
                    </p>

                    <div className="mt-12 prose prose-gray max-w-none">
                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">1. Introduction</h2>
                        <p className="mt-4 text-gray-600">
                            Quantum Forge (&quot;we,&quot; &quot;our,&quot; or &quot;us&quot;) operates the A2A Server MCP platform. This Privacy Policy
                            explains how we collect, use, disclose, and safeguard your information when you use our
                            service.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">2. Information We Collect</h2>

                        <h3 className="text-xl font-semibold text-gray-900 mt-8">Information You Provide</h3>
                        <ul className="mt-4 space-y-2 text-gray-600">
                            <li>• Account registration information (name, email, company)</li>
                            <li>• Contact form submissions</li>
                            <li>• Payment and billing information (processed by Stripe)</li>
                            <li>• Communications with our support team</li>
                        </ul>

                        <h3 className="text-xl font-semibold text-gray-900 mt-8">Information Collected Automatically</h3>
                        <ul className="mt-4 space-y-2 text-gray-600">
                            <li>• Usage data and analytics (via privacy-focused Plausible Analytics)</li>
                            <li>• Server logs (IP addresses, request times, endpoints accessed)</li>
                            <li>• Device and browser information</li>
                        </ul>

                        <h3 className="text-xl font-semibold text-gray-900 mt-8">Agent Communication Data</h3>
                        <p className="mt-4 text-gray-600">
                            When using A2A Server MCP, agent messages may be temporarily processed through our servers.
                            For self-hosted deployments, all data remains within your infrastructure.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">3. How We Use Your Information</h2>
                        <ul className="mt-4 space-y-2 text-gray-600">
                            <li>• Provide, maintain, and improve our services</li>
                            <li>• Process transactions and send related information</li>
                            <li>• Send administrative messages and updates</li>
                            <li>• Respond to customer service requests</li>
                            <li>• Monitor usage patterns to improve user experience</li>
                            <li>• Detect and prevent fraud or abuse</li>
                        </ul>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">4. Data Sharing</h2>
                        <p className="mt-4 text-gray-600">
                            We do not sell your personal information. We may share data with:
                        </p>
                        <ul className="mt-4 space-y-2 text-gray-600">
                            <li>• Service providers (hosting, payment processing, analytics)</li>
                            <li>• Legal authorities when required by law</li>
                            <li>• Business successors in case of merger or acquisition</li>
                        </ul>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">5. Data Security</h2>
                        <p className="mt-4 text-gray-600">
                            We implement industry-standard security measures including:
                        </p>
                        <ul className="mt-4 space-y-2 text-gray-600">
                            <li>• TLS 1.3 encryption for all data in transit</li>
                            <li>• AES-256 encryption for data at rest</li>
                            <li>• Regular security audits and penetration testing</li>
                            <li>• SOC 2 Type II compliance (Enterprise tier)</li>
                        </ul>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">6. Data Retention</h2>
                        <p className="mt-4 text-gray-600">
                            We retain your information for as long as your account is active or as needed to provide
                            services. You may request deletion of your data at any time by contacting us.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">7. Your Rights</h2>
                        <p className="mt-4 text-gray-600">
                            Depending on your location, you may have the right to:
                        </p>
                        <ul className="mt-4 space-y-2 text-gray-600">
                            <li>• Access your personal data</li>
                            <li>• Correct inaccurate data</li>
                            <li>• Delete your data</li>
                            <li>• Export your data in a portable format</li>
                            <li>• Opt-out of marketing communications</li>
                        </ul>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">8. International Transfers</h2>
                        <p className="mt-4 text-gray-600">
                            Your information may be processed in the United States or other countries. We ensure
                            appropriate safeguards are in place for international data transfers.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">9. Children&apos;s Privacy</h2>
                        <p className="mt-4 text-gray-600">
                            Our service is not directed to individuals under 18. We do not knowingly collect
                            information from children.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">10. Changes to This Policy</h2>
                        <p className="mt-4 text-gray-600">
                            We may update this Privacy Policy periodically. We will notify you of material changes
                            via email or prominent notice on our website.
                        </p>

                        <h2 className="text-2xl font-semibold text-gray-900 mt-12">11. Contact Us</h2>
                        <p className="mt-4 text-gray-600">
                            For questions about this Privacy Policy or our practices:
                        </p>
                        <ul className="mt-4 space-y-2 text-gray-600">
                            <li>• Email: privacy@quantum-forge.net</li>
                            <li>• GitHub: github.com/rileyseaburg/codetether/issues</li>
                        </ul>
                    </div>
                </div>
            </Container>
        </div>
    )
}
