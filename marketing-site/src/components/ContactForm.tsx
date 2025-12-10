'use client'

import { useState } from 'react'
import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

export function ContactForm() {
    const [submitted, setSubmitted] = useState(false)

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault()
        // In production, this would submit to your backend
        setSubmitted(true)
    }

    return (
        <section
            id="contact"
            aria-labelledby="contact-title"
            className="border-t border-gray-200 py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl">
                    <div className="text-center">
                        <h2
                            id="contact-title"
                            className="text-3xl font-medium tracking-tight text-gray-900"
                        >
                            Ready to scale your AI agents?
                        </h2>
                        <p className="mt-2 text-lg text-gray-600">
                            Talk to our team about your use case. We'll help you get started.
                        </p>
                    </div>

                    {submitted ? (
                        <div className="mt-10 rounded-2xl bg-green-50 p-8 text-center">
                            <div className="text-4xl">🎉</div>
                            <h3 className="mt-4 text-lg font-semibold text-green-900">
                                Thanks for reaching out!
                            </h3>
                            <p className="mt-2 text-green-700">
                                We'll be in touch within 24 hours.
                            </p>
                        </div>
                    ) : (
                        <form onSubmit={handleSubmit} className="mt-10 space-y-6">
                            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                                <div>
                                    <label
                                        htmlFor="name"
                                        className="block text-sm font-medium text-gray-700"
                                    >
                                        Name
                                    </label>
                                    <input
                                        type="text"
                                        id="name"
                                        name="name"
                                        required
                                        className="mt-1 block w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 placeholder-gray-400 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                                        placeholder="Jane Smith"
                                    />
                                </div>
                                <div>
                                    <label
                                        htmlFor="email"
                                        className="block text-sm font-medium text-gray-700"
                                    >
                                        Work Email
                                    </label>
                                    <input
                                        type="email"
                                        id="email"
                                        name="email"
                                        required
                                        className="mt-1 block w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 placeholder-gray-400 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                                        placeholder="jane@company.com"
                                    />
                                </div>
                            </div>
                            <div>
                                <label
                                    htmlFor="company"
                                    className="block text-sm font-medium text-gray-700"
                                >
                                    Company
                                </label>
                                <input
                                    type="text"
                                    id="company"
                                    name="company"
                                    className="mt-1 block w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 placeholder-gray-400 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                                    placeholder="Acme Inc."
                                />
                            </div>
                            <div>
                                <label
                                    htmlFor="use-case"
                                    className="block text-sm font-medium text-gray-700"
                                >
                                    What would you like to build?
                                </label>
                                <select
                                    id="use-case"
                                    name="use-case"
                                    className="mt-1 block w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
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
                                    className="block text-sm font-medium text-gray-700"
                                >
                                    Tell us more
                                </label>
                                <textarea
                                    id="message"
                                    name="message"
                                    rows={4}
                                    className="mt-1 block w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 placeholder-gray-400 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                                    placeholder="Describe your AI agent use case..."
                                />
                            </div>
                            <div className="text-center">
                                <Button type="submit" color="cyan">
                                    Request Demo
                                </Button>
                            </div>
                            <p className="text-center text-xs text-gray-500">
                                By submitting, you agree to our{' '}
                                <a href="/privacy" className="underline hover:text-gray-700">
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
