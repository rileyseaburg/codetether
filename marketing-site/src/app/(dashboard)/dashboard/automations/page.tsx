'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'

interface AutomationTemplate {
  id: string
  name: string
  description: string
  category: string
  required_inputs: Array<{
    name: string
    label: string
    type: string
    required?: boolean
    default?: string
    options?: string[]
  }>
}

interface Automation {
  id: string
  name: string
  status: string
  last_run_at: string | null
  run_count: number
  created_at: string
}

const CATEGORY_ICONS: Record<string, string> = {
  research: '🔍',
  content: '✍️',
  outreach: '📧',
  data: '📊',
}

const CATEGORY_COLORS: Record<string, string> = {
  research: 'bg-blue-100 text-blue-800',
  content: 'bg-purple-100 text-purple-800',
  outreach: 'bg-green-100 text-green-800',
  data: 'bg-orange-100 text-orange-800',
}

export default function AutomationsPage() {
  const [templates, setTemplates] = useState<AutomationTemplate[]>([])
  const [automations, setAutomations] = useState<Automation[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<AutomationTemplate | null>(null)
  const [formData, setFormData] = useState<Record<string, string>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitResult, setSubmitResult] = useState<{ success: boolean; message: string } | null>(null)
  const [activeTab, setActiveTab] = useState<'new' | 'history'>('new')

  // Default templates if API fails
  const defaultTemplates: AutomationTemplate[] = [
    {
      id: 'tpl_competitor_intel',
      name: 'Competitor Intelligence Report',
      description: 'Research your competitors and get a detailed analysis of their online presence, marketing, and positioning.',
      category: 'research',
      required_inputs: [
        { name: 'company_name', label: 'Your Company Name', type: 'text', required: true },
        { name: 'industry', label: 'Your Industry', type: 'text', required: true },
        { name: 'competitors', label: 'Competitor Names (comma-separated)', type: 'text', required: true },
      ],
    },
    {
      id: 'tpl_content_batch',
      name: 'Weekly Content Batch',
      description: "Generate a week's worth of social media content tailored to your brand voice.",
      category: 'content',
      required_inputs: [
        { name: 'brand_name', label: 'Brand/Company Name', type: 'text', required: true },
        { name: 'business_type', label: 'What does your business do?', type: 'text', required: true },
        { name: 'target_audience', label: 'Who is your target audience?', type: 'text', required: true },
        { name: 'topics', label: 'Key topics to cover', type: 'text', required: true },
      ],
    },
    {
      id: 'tpl_lead_research',
      name: 'Lead Research & Enrichment',
      description: 'Research potential leads and gather detailed information for personalized outreach.',
      category: 'research',
      required_inputs: [
        { name: 'my_company', label: 'Your Company Name', type: 'text', required: true },
        { name: 'leads', label: 'Companies/People to Research (one per line)', type: 'textarea', required: true },
        { name: 'what_we_sell', label: 'What do you sell?', type: 'text', required: true },
        { name: 'ideal_customer', label: 'Describe your ideal customer', type: 'text', required: true },
      ],
    },
    {
      id: 'tpl_email_sequence',
      name: 'Outreach Email Sequence',
      description: 'Generate a personalized cold outreach email sequence for sales or partnerships.',
      category: 'outreach',
      required_inputs: [
        { name: 'purpose', label: 'Purpose of outreach', type: 'select', options: ['Sales', 'Partnership', 'Investor', 'Press/Media', 'Other'], required: true },
        { name: 'company_context', label: 'About your company (2-3 sentences)', type: 'textarea', required: true },
        { name: 'recipient_profile', label: 'Who are you reaching out to?', type: 'text', required: true },
        { name: 'value_prop', label: 'Your key value proposition', type: 'text', required: true },
        { name: 'desired_outcome', label: 'What do you want them to do?', type: 'text', required: true },
      ],
    },
  ]

  useEffect(() => {
    // In MVP, use default templates
    setTemplates(defaultTemplates)
    
    // TODO: Fetch from API
    // const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://codetether.com'
    // fetch(`${apiUrl}/v1/automations/templates`)
    //   .then(res => res.json())
    //   .then(data => setTemplates(data))
    //   .catch(() => setTemplates(defaultTemplates))
  }, [])

  const handleTemplateSelect = (template: AutomationTemplate) => {
    setSelectedTemplate(template)
    setFormData({})
    setSubmitResult(null)
  }

  const handleInputChange = (name: string, value: string) => {
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedTemplate) return

    setIsSubmitting(true)
    setSubmitResult(null)

    try {
       const token = localStorage.getItem('a2a_token')
       const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

      // Build the prompt from template
      let prompt = selectedTemplate.name + '\n\n'
      for (const input of selectedTemplate.required_inputs) {
        const value = formData[input.name] || input.default || ''
        prompt += `${input.label}: ${value}\n`
      }

      const response = await fetch(`${apiUrl}/v1/opencode/tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({
          title: selectedTemplate.name,
          prompt,
          agent_type: 'general',
          priority: 1,
          metadata: {
            template_id: selectedTemplate.id,
            category: selectedTemplate.category,
            inputs: formData,
          },
        }),
      })

      if (response.ok) {
        const result = await response.json()
        setSubmitResult({
          success: true,
          message: `Automation started! Task ID: ${result.id}. You'll receive an email when it's complete.`,
        })
        // Reset form
        setFormData({})
        setSelectedTemplate(null)
      } else {
        const error = await response.json().catch(() => ({}))
        setSubmitResult({
          success: false,
          message: error.detail || 'Failed to start automation. Please try again.',
        })
      }
    } catch (err) {
      setSubmitResult({
        success: false,
        message: 'Failed to connect to server. Please check your connection.',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const renderInput = (input: AutomationTemplate['required_inputs'][0]) => {
    const value = formData[input.name] || ''
    const baseClasses = "w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"

    if (input.type === 'textarea') {
      return (
        <textarea
          key={input.name}
          name={input.name}
          value={value}
          onChange={(e) => handleInputChange(input.name, e.target.value)}
          required={input.required}
          rows={3}
          className={baseClasses}
          placeholder={input.label}
        />
      )
    }

    if (input.type === 'select' && input.options) {
      return (
        <select
          key={input.name}
          name={input.name}
          value={value}
          onChange={(e) => handleInputChange(input.name, e.target.value)}
          required={input.required}
          className={baseClasses}
        >
          <option value="">Select {input.label}</option>
          {input.options.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      )
    }

    return (
      <input
        key={input.name}
        type="text"
        name={input.name}
        value={value}
        onChange={(e) => handleInputChange(input.name, e.target.value)}
        required={input.required}
        className={baseClasses}
        placeholder={input.label}
      />
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Automations
              </h1>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Describe what you need done. We handle the rest.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setActiveTab('new')}
                className={`px-4 py-2 rounded-md text-sm font-medium ${
                  activeTab === 'new'
                    ? 'bg-cyan-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                New Automation
              </button>
              <button
                onClick={() => setActiveTab('history')}
                className={`px-4 py-2 rounded-md text-sm font-medium ${
                  activeTab === 'history'
                    ? 'bg-cyan-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                History
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {submitResult && (
          <div
            className={`mb-6 p-4 rounded-md ${
              submitResult.success
                ? 'bg-green-50 text-green-800 border border-green-200'
                : 'bg-red-50 text-red-800 border border-red-200'
            }`}
          >
            {submitResult.message}
          </div>
        )}

        {activeTab === 'new' && (
          <>
            {!selectedTemplate ? (
              /* Template Selection */
              <div>
                <h2 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                  Choose an automation template
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {templates.map((template) => (
                    <button
                      key={template.id}
                      onClick={() => handleTemplateSelect(template)}
                      className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-md transition-shadow text-left border border-gray-200 dark:border-gray-700"
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-2xl">
                          {CATEGORY_ICONS[template.category] || '⚡'}
                        </span>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-semibold text-gray-900 dark:text-white">
                              {template.name}
                            </h3>
                            <span
                              className={`text-xs px-2 py-0.5 rounded-full ${
                                CATEGORY_COLORS[template.category] || 'bg-gray-100 text-gray-800'
                              }`}
                            >
                              {template.category}
                            </span>
                          </div>
                          <p className="text-sm text-gray-600 dark:text-gray-400">
                            {template.description}
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>

                {/* Custom automation option */}
                <div className="mt-8 p-6 bg-gray-100 dark:bg-gray-800 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600">
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                    Need something custom?
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                    Describe any task in plain English and we'll figure out how to do it.
                  </p>
                  <Link
                    href="/dashboard/automations/custom"
                    className="inline-flex items-center px-4 py-2 bg-cyan-600 text-white rounded-md hover:bg-cyan-700 transition-colors text-sm font-medium"
                  >
                    Create Custom Automation
                  </Link>
                </div>
              </div>
            ) : (
              /* Template Form */
              <div className="max-w-2xl">
                <button
                  onClick={() => setSelectedTemplate(null)}
                  className="mb-4 text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1"
                >
                  ← Back to templates
                </button>

                <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                  <div className="flex items-center gap-3 mb-6">
                    <span className="text-3xl">
                      {CATEGORY_ICONS[selectedTemplate.category] || '⚡'}
                    </span>
                    <div>
                      <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                        {selectedTemplate.name}
                      </h2>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {selectedTemplate.description}
                      </p>
                    </div>
                  </div>

                  <form onSubmit={handleSubmit} className="space-y-4">
                    {selectedTemplate.required_inputs.map((input) => (
                      <div key={input.name}>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          {input.label}
                          {input.required && <span className="text-red-500 ml-1">*</span>}
                        </label>
                        {renderInput(input)}
                      </div>
                    ))}

                    <div className="pt-4">
                      <button
                        type="submit"
                        disabled={isSubmitting}
                        className="w-full px-4 py-3 bg-cyan-600 text-white rounded-md hover:bg-cyan-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isSubmitting ? 'Starting automation...' : 'Run Automation'}
                      </button>
                      <p className="mt-2 text-xs text-gray-500 text-center">
                        Results will be emailed to you when complete.
                      </p>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === 'history' && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
            <div className="p-6">
              <h2 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                Recent Automations
              </h2>
              {automations.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <p className="text-lg mb-2">No automations yet</p>
                  <p className="text-sm">
                    Run your first automation to see it here.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {automations.map((automation) => (
                    <div
                      key={automation.id}
                      className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg"
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="font-medium text-gray-900 dark:text-white">
                            {automation.name}
                          </h3>
                          <p className="text-sm text-gray-500">
                            {automation.run_count} runs · Last run: {automation.last_run_at || 'Never'}
                          </p>
                        </div>
                        <span
                          className={`px-2 py-1 text-xs rounded-full ${
                            automation.status === 'active'
                              ? 'bg-green-100 text-green-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {automation.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
