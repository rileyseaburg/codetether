'use client'

import { useState } from 'react'
import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

export function ContactForm() {
    const [submitted, setSubmitted] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault()
        setLoading(true)
        setError(null)

        const formData = new FormData(e.currentTarget)
        const data = {
            name: formData.get('name') as string,
            email: formData.get('email') as string,
            company: formData.get('company') as string,
            useCase: formData.get('use-case') as string,
            message: formData.get('message') as string,
        }

        try {
            const response = await fetch('/api/contact', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            })

            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.error || 'Failed to submit form')
            }

            setSubmitted(true)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Something went wrong')
        } finally {
            setLoading(false)
        }
    }

    return (
        <section
            id="contact"
            aria-labelledby="contact-title"
            className="border-t border-gray-200 dark:border-gray-800 py-20 sm:py-32 bg-white dark:bg-gray-950"
        >
            <Container>
                <div className="mx-auto max-w-2xl">
                    <div className="text-center">
                        <h2
                            id="contact-title"
                            className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white"
                        >
                            Ready to Deploy Agents You Can Actually Trust?
                        </h2>
                        <p className="mt-2 text-lg text-gray-600 dark:text-gray-300">
                            Tell us about your infrastructure. We&apos;ll help you deploy CodeTether.
                        </p>
                    </div>

                    {submitted ? (
                        <div className="mt-10 rounded-2xl bg-green-50 dark:bg-green-900/20 p-8 text-center">
                            <div className="text-4xl">🎉</div>
                            <h3 className="mt-4 text-lg font-semibold text-green-900 dark:text-green-400">
                                Thanks for reaching out!
                            </h3>
                            <p className="mt-2 text-green-700 dark:text-green-300">
                                We'll be in touch within 24 hours.
                            </p>
                        </div>
                    ) : (
                        <form onSubmit={handleSubmit} className="mt-10 space-y-6">
                            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                                <div>
                                    <label
                                        htmlFor="name"
                                        className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                                    >
                                        Name
                                    </label>
                                    <input
                                        type="text"
                                        id="name"
                                        name="name"
                                        required
                                        className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                                        placeholder="Jane Smith"
                                    />
                                </div>
                                <div>
                                    <label
                                        htmlFor="email"
                                        className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                                    >
                                        Work Email
                                    </label>
                                    <input
                                        type="email"
                                        id="email"
                                        name="email"
                                        required
                                        className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                                        placeholder="jane@company.com"
                                    />
                                </div>
                            </div>
                            <div>
                                <label
                                    htmlFor="company"
                                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                                >
                                    Company
                                </label>
                                <input
                                    type="text"
                                    id="company"
                                    name="company"
                                    className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                                    placeholder="Acme Inc."
                                />
                            </div>
                            <div>
                                <label
                                    htmlFor="use-case"
                                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                                >
                                    What would you like to build?
                                </label>
                                <select
                                    id="use-case"
                                    name="use-case"
                                    className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2 text-gray-900 dark:text-white focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                                >
                                    <option value="">Select a use case...</option>
                                    <option value="coding">AI Coding Assistants</option>
                                    <option value="support">Customer Support Automation</option>
                                    <option value="data">Data Pipeline Orchestration</option>
                                    <option value="research">Research & Analysis</option>
                                    <option value="devops">DevOps Automation</option>
                                    <option value="content">Content Generation</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                            <div>
                                <label
                                    htmlFor="message"
                                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                                >
                                    Tell us more
                                </label>
                                <textarea
                                    id="message"
                                    name="message"
                                    rows={4}
                                    className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                                    placeholder="Describe your AI agent use case..."
                                />
                            </div>
                            {error && (
                                <div className="rounded-lg bg-red-50 dark:bg-red-900/20 p-4 text-center text-red-700 dark:text-red-300">
                                    {error}
                                </div>
                            )}
                            <div className="text-center">
                                <Button type="submit" color="cyan" disabled={loading}>
                                    {loading ? 'Submitting...' : 'Request Demo'}
                                </Button>
                            </div>
                            <p className="text-center text-xs text-gray-500 dark:text-gray-400">
                                By submitting, you agree to our{' '}
                                <a href="/privacy" className="underline hover:text-gray-700 dark:hover:text-gray-300">
                                    Privacy Policy
                                </a>
                                .
                            </p>
                        </form>
                    )}
                </div>
            </Container>
        </section>
    )
}
