'use client'

import { useState } from 'react'
import Link from 'next/link'

export default function CustomAutomationPage() {
  const [prompt, setPrompt] = useState('')
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    setResult(null)

    try {
      const token = localStorage.getItem('a2a_token')
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://codetether.com'

      // Use the automation API which queues tasks and sends email notifications
      const response = await fetch(`${apiUrl}/v1/automation/tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({
          title: 'Custom Automation Request',
          description: prompt,
          agent_type: 'general',
          priority: 1,
          notify_email: email || undefined,  // Email goes to worker queue for notification
        }),
      })

      if (response.ok) {
        const data = await response.json()
        setResult({
          success: true,
          message: `Automation started! Task ID: ${data.task_id}. Results will be emailed to you when complete.`,
        })
        setPrompt('')
      } else {
        const error = await response.json().catch(() => ({}))
        setResult({
          success: false,
          message: error.detail || 'Failed to start automation. Please try again.',
        })
      }
    } catch (err) {
      setResult({
        success: false,
        message: 'Failed to connect to server. Please check your connection.',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const examples = [
    "Research the top 5 CRM software companies and compare their pricing, features, and customer reviews",
    "Find 20 potential customers for my SaaS product in the healthcare space, including company name, size, and likely decision maker",
    "Write a week's worth of LinkedIn posts about AI productivity tips for small business owners",
    "Create a competitive analysis comparing Stripe, Square, and PayPal for e-commerce businesses",
    "Draft 3 cold outreach emails for selling marketing automation software to agency owners",
  ]

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 shadow">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Link
            href="/dashboard/automations"
            className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1 mb-4"
          >
            ← Back to automations
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Custom Automation
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Describe any task in plain English. We'll figure out how to do it.
          </p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {result && (
          <div
            className={`mb-6 p-4 rounded-md ${
              result.success
                ? 'bg-green-50 text-green-800 border border-green-200'
                : 'bg-red-50 text-red-800 border border-red-200'
            }`}
          >
            {result.message}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              What do you need done?
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={6}
              required
              className="w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500 text-base"
              placeholder="Describe the task you want automated. Be as specific as possible about what you need, including any context, preferences, or requirements."
            />

            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Email for results (optional)
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
                placeholder="you@example.com"
              />
              <p className="mt-1 text-xs text-gray-500">
                If not provided, we'll use your account email.
              </p>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || !prompt.trim()}
              className="mt-6 w-full px-4 py-3 bg-cyan-600 text-white rounded-md hover:bg-cyan-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Starting automation...' : 'Run Automation'}
            </button>
          </div>
        </form>

        {/* Example prompts */}
        <div className="mt-8">
          <h2 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
            Example requests
          </h2>
          <div className="grid gap-3">
            {examples.map((example, index) => (
              <button
                key={index}
                onClick={() => setPrompt(example)}
                className="text-left p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-cyan-500 hover:shadow-sm transition-all text-sm text-gray-700 dark:text-gray-300"
              >
                <span className="text-cyan-600 font-medium mr-2">Try:</span>
                {example}
              </button>
            ))}
          </div>
        </div>

        {/* How it works */}
        <div className="mt-12 p-6 bg-gray-100 dark:bg-gray-800 rounded-lg">
          <h2 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
            How it works
          </h2>
          <ol className="space-y-3 text-sm text-gray-600 dark:text-gray-400">
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-cyan-100 text-cyan-700 flex items-center justify-center font-medium text-xs">
                1
              </span>
              <span>Describe what you need done in plain English</span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-cyan-100 text-cyan-700 flex items-center justify-center font-medium text-xs">
                2
              </span>
              <span>Our AI agents break down the task and get to work</span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-cyan-100 text-cyan-700 flex items-center justify-center font-medium text-xs">
                3
              </span>
              <span>You receive results via email when complete</span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-cyan-100 text-cyan-700 flex items-center justify-center font-medium text-xs">
                4
              </span>
              <span>Reply to continue the conversation or refine results</span>
            </li>
          </ol>
        </div>
      </div>
    </div>
  )
}
