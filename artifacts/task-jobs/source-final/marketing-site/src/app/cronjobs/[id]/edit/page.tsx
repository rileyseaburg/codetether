'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Save, Clock, AlertCircle, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { useTenantApi } from '@/hooks/useTenantApi';
import { WorkerSelector } from '@/components/WorkerSelector';

interface Props {
  params: Promise<{ id: string }>;
}

interface WorkerOption {
  worker_id: string;
  name?: string;
  status?: string;
  last_seen?: string;
  worker_runtime?: 'rust' | 'python';
  worker_runtime_label?: string;
  is_sse_connected?: boolean;
}

interface GeneratedCronjobDraft {
  name?: string;
  description?: string;
  cron_expression?: string;
  timezone?: string;
  task_template?: {
    title?: string;
    prompt?: string;
    codebase_id?: string;
    agent_type?: string;
  };
}

function extractJsonBlock(text: string): string {
  const fenced = text.match(/```json\s*([\s\S]*?)\s*```/i);
  if (fenced && fenced[1]) {
    return fenced[1].trim();
  }

  const start = text.indexOf('{');
  const end = text.lastIndexOf('}');
  if (start >= 0 && end > start) {
    return text.slice(start, end + 1);
  }
  return text.trim();
}

export default function EditCronjobPage({ params }: Props) {
  const { id } = use(params);
  const router = useRouter();
  const { tenantFetch } = useTenantApi();
  const isNew = id === 'new';
  
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    cron_expression: '',
    timezone: 'UTC',
    enabled: true,
    task_template: {
      title: '',
      prompt: '',
      codebase_id: '',
      agent_type: 'default',
    },
  });
  
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewRuns, setPreviewRuns] = useState<string[]>([]);
  const [workers, setWorkers] = useState<WorkerOption[]>([]);
  const [selectedWorkerId, setSelectedWorkerId] = useState('');
  const [assistantPrompt, setAssistantPrompt] = useState('');
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState<string | null>(null);
  const [assistantError, setAssistantError] = useState<string | null>(null);
  const [assistantDraft, setAssistantDraft] = useState<GeneratedCronjobDraft | null>(null);
  const [assistantRawResult, setAssistantRawResult] = useState<string | null>(null);

  useEffect(() => {
    if (!isNew) {
      fetchJob();
    }
  }, [isNew]);

  useEffect(() => {
    fetchWorkers();
  }, []);

  useEffect(() => {
    if (formData.cron_expression) {
      validateAndPreview();
    }
  }, [formData.cron_expression, formData.timezone]);

  async function fetchJob() {
    try {
      const { data, error } = await tenantFetch<any>(`/v1/cronjobs/${id}`);
      if (error || !data) throw new Error(error || 'Failed to fetch cronjob');
      setFormData({
        name: data.name || '',
        description: data.description || '',
        cron_expression: data.cron_expression || '',
        timezone: data.timezone || 'UTC',
        enabled: data.enabled ?? true,
        task_template: data.task_template || {
          title: '',
          prompt: '',
          codebase_id: '',
          agent_type: 'default',
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cronjob');
    } finally {
      setLoading(false);
    }
  }

  async function fetchWorkers() {
    try {
      const [workersResponse, connectedResponse] = await Promise.all([
        tenantFetch<WorkerOption[]>('/v1/agent/workers'),
        tenantFetch<{ workers?: Array<{ worker_id?: string; agent_name?: string; last_heartbeat?: string }> }>(
          '/v1/worker/connected'
        ),
      ]);

      if (workersResponse.error) throw new Error(workersResponse.error);

      const connectedWorkers = connectedResponse.data?.workers || [];
      const connectedMap = new Map(
        connectedWorkers
          .filter((w) => w.worker_id)
          .map((w) => [
            String(w.worker_id),
            {
              name: w.agent_name,
              last_seen: w.last_heartbeat,
            },
          ])
      );

      const availableWorkers = (workersResponse.data || []).map((worker) => {
        const connected = connectedMap.get(worker.worker_id);
        return {
          ...worker,
          name: connected?.name || worker.name,
          last_seen: connected?.last_seen || worker.last_seen,
          is_sse_connected: Boolean(connected),
        };
      });
      setWorkers(availableWorkers);
    } catch {
      setWorkers([]);
    }
  }

  async function validateAndPreview() {
    try {
      const { data } = await tenantFetch<{
        valid?: boolean;
        error?: string;
        next_runs?: string[];
      }>('/v1/cronjobs/validate-cron', {
        method: 'POST',
        body: JSON.stringify({
          expression: formData.cron_expression,
          timezone: formData.timezone,
        }),
      });

      if (data?.valid) {
        setPreviewRuns(data.next_runs || []);
        setError(null);
      } else {
        setPreviewRuns([]);
        if (formData.cron_expression) {
          setError(`Invalid cron expression: ${data?.error || 'Invalid expression'}`);
        }
      }
    } catch {
      setPreviewRuns([]);
    }
  }

  function buildAssistantTaskPrompt(intent: string): string {
    const existingContext = {
      name: formData.name || null,
      description: formData.description || null,
      timezone: formData.timezone || 'UTC',
      task_template: {
        title: formData.task_template.title || null,
        prompt: formData.task_template.prompt || null,
        codebase_id: formData.task_template.codebase_id || null,
        agent_type: formData.task_template.agent_type || 'default',
      },
    };

    return [
      'You are a cronjob scheduling assistant.',
      'Create a safe, practical cronjob draft from the user intent.',
      'Respond with ONLY valid JSON (no markdown) using this exact schema:',
      '{',
      '  "name": "string",',
      '  "description": "string",',
      '  "cron_expression": "string",',
      '  "timezone": "string",',
      '  "task_template": {',
      '    "title": "string",',
      '    "prompt": "string",',
      '    "codebase_id": "string",',
      '    "agent_type": "default|explorer|builder|reviewer"',
      '  }',
      '}',
      'Rules:',
      '- Use 5-field cron format: minute hour day month weekday.',
      '- Default timezone to UTC if user did not specify.',
      '- Keep task prompt concise and actionable.',
      '- Prefer conservative schedules (avoid too-frequent runs unless asked).',
      '',
      `User intent: ${intent}`,
      `Current form context (may include partial data): ${JSON.stringify(existingContext)}`,
    ].join('\n');
  }

  async function pollTaskResult(taskId: string): Promise<any> {
    let attempts = 0;
    let latestStatus: string | null = null;
    while (attempts < 90) {
      const { data, error } = await tenantFetch<any>(`/v1/agent/tasks/${taskId}`);
      if (error) throw new Error(error);
      if (!data) throw new Error('Task not found');
      latestStatus = data.status || null;

      if (data.status === 'completed') return data;
      if (data.status === 'failed' || data.status === 'cancelled') {
        throw new Error(data.error || `Task ${data.status}`);
      }

      attempts += 1;
      setAssistantStatus(`Generating draft... (${attempts * 2}s)`);
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }

    throw new Error(
      `Timed out waiting for worker response (task: ${taskId}, last status: ${
        latestStatus || 'unknown'
      }). Try Auto-select worker or choose an online worker.`
    );
  }

  async function generateWithAssistant() {
    if (!assistantPrompt.trim()) {
      setAssistantError('Describe what you want to automate first.');
      return;
    }

    setAssistantLoading(true);
    setAssistantError(null);
    setAssistantStatus('Submitting request to worker...');
    setAssistantDraft(null);
    setAssistantRawResult(null);

    try {
      const targetableWorkers = workers.filter((w) => w.is_sse_connected);
      if (targetableWorkers.length === 0) {
        throw new Error(
          'No codetether-agent workers are currently connected. Connect a worker to /v1/worker/tasks/stream, then try again.'
        );
      }

      const taskPayload: Record<string, unknown> = {
        title: `Cronjob draft: ${assistantPrompt.slice(0, 60)}`,
        prompt: buildAssistantTaskPrompt(assistantPrompt.trim()),
        agent_type: 'general',
        priority: 5,
        metadata: {
          feature: 'cronjob_assistant',
          requested_at: new Date().toISOString(),
        },
      };

      if (selectedWorkerId) {
        const selectedWorker = workers.find((w) => w.worker_id === selectedWorkerId);
        if (selectedWorker && !selectedWorker.is_sse_connected) {
          throw new Error(
            `Selected worker "${selectedWorker.name || selectedWorker.worker_id}" is not connected via codetether-agent SSE. Choose Auto-select worker or a connected worker.`
          );
        }

        taskPayload.metadata = {
          ...(taskPayload.metadata as Record<string, unknown>),
          target_worker_id: selectedWorkerId,
        };
      }

      const { data, error } = await tenantFetch<any>('/v1/agent/tasks', {
        method: 'POST',
        body: JSON.stringify(taskPayload),
      });
      if (error || !data?.id) {
        throw new Error(error || 'Failed to create worker task');
      }

      const completedTask = await pollTaskResult(data.id as string);
      const rawResult = String(completedTask.result || '').trim();
      if (!rawResult) {
        throw new Error('Worker completed without a result');
      }

      setAssistantRawResult(rawResult);
      const parsed = JSON.parse(extractJsonBlock(rawResult)) as GeneratedCronjobDraft;
      setAssistantDraft(parsed);
      setAssistantStatus('Draft ready. Review and apply.');
    } catch (assistantErr) {
      setAssistantError(
        assistantErr instanceof Error ? assistantErr.message : 'Failed to generate draft'
      );
      setAssistantStatus(null);
    } finally {
      setAssistantLoading(false);
    }
  }

  function applyAssistantDraft() {
    if (!assistantDraft) return;

    setFormData((current) => ({
      ...current,
      name: assistantDraft.name || current.name,
      description: assistantDraft.description || current.description,
      cron_expression: assistantDraft.cron_expression || current.cron_expression,
      timezone: assistantDraft.timezone || current.timezone,
      task_template: {
        ...current.task_template,
        title: assistantDraft.task_template?.title || current.task_template.title,
        prompt: assistantDraft.task_template?.prompt || current.task_template.prompt,
        codebase_id:
          assistantDraft.task_template?.codebase_id || current.task_template.codebase_id,
        agent_type:
          assistantDraft.task_template?.agent_type || current.task_template.agent_type,
      },
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const url = isNew ? '/v1/cronjobs' : `/v1/cronjobs/${id}`;
      const method = isNew ? 'POST' : 'PUT';
      const { error } = await tenantFetch(url, {
        method,
        body: JSON.stringify(formData),
      });
      if (error) throw new Error(error);

      router.push('/cronjobs');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  const cronPresets = [
    { label: 'Every minute', value: '* * * * *' },
    { label: 'Every 5 minutes', value: '*/5 * * * *' },
    { label: 'Every hour', value: '0 * * * *' },
    { label: 'Daily at midnight', value: '0 0 * * *' },
    { label: 'Daily at noon', value: '0 12 * * *' },
    { label: 'Weekly (Sunday)', value: '0 0 * * 0' },
    { label: 'Monthly (1st)', value: '0 0 1 * *' },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto text-gray-900 dark:text-gray-100">
      <div className="flex items-center mb-6">
        <Link
          href="/cronjobs"
          className="inline-flex items-center text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mr-4"
        >
          <ArrowLeft className="w-5 h-5 mr-2" />
          Back
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {isNew ? 'Create Cronjob' : 'Edit Cronjob'}
        </h1>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-4 py-3 rounded flex items-center">
          <AlertCircle className="w-5 h-5 mr-2" />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {isNew && (
          <div className="bg-gradient-to-r from-indigo-50 to-cyan-50 dark:from-gray-900 dark:to-gray-900 border border-indigo-200 dark:border-gray-700 rounded-lg p-6">
            <div className="flex items-center mb-3">
              <Sparkles className="w-5 h-5 mr-2 text-indigo-600 dark:text-indigo-400" />
              <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">AI-Assisted Setup</h2>
            </div>
            <p className="text-sm text-gray-700 dark:text-gray-300 mb-4">
              Describe the automation you want, and a worker will draft the schedule and task prompt.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  What should this cronjob do?
                </label>
                <textarea
                  value={assistantPrompt}
                  onChange={(e) => setAssistantPrompt(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Example: Every weekday at 8am ET, summarize yesterday's production errors and post a concise report."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Worker (optional)
                </label>
                <WorkerSelector
                  value={selectedWorkerId}
                  onChange={setSelectedWorkerId}
                  workers={workers}
                  onlyConnected={false}
                  disableDisconnected
                  includeAutoOption
                  autoOptionLabel="Auto-select worker"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Only workers marked <span className="font-medium">connected</span> can be targeted.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={generateWithAssistant}
                  disabled={assistantLoading}
                  className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
                >
                  <Sparkles className="w-4 h-4 mr-2" />
                  {assistantLoading ? 'Generating...' : 'Generate Draft'}
                </button>
                {assistantStatus && <p className="text-sm text-gray-600 dark:text-gray-400">{assistantStatus}</p>}
              </div>

              {assistantError && (
                <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-3 py-2 rounded text-sm">
                  {assistantError}
                </div>
              )}

              {assistantDraft && (
                <div className="bg-white dark:bg-gray-900 border border-indigo-200 rounded-md p-4">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-2">Suggested Draft</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-gray-700 dark:text-gray-300">
                    <p><span className="font-medium">Name:</span> {assistantDraft.name || '-'}</p>
                    <p><span className="font-medium">Schedule:</span> {assistantDraft.cron_expression || '-'}</p>
                    <p><span className="font-medium">Timezone:</span> {assistantDraft.timezone || '-'}</p>
                    <p><span className="font-medium">Agent Type:</span> {assistantDraft.task_template?.agent_type || '-'}</p>
                  </div>
                  <button
                    type="button"
                    onClick={applyAssistantDraft}
                    className="mt-3 inline-flex items-center px-3 py-2 border border-indigo-300 dark:border-indigo-700 text-indigo-700 dark:text-indigo-300 rounded-md hover:bg-indigo-50 dark:hover:bg-indigo-950/40"
                  >
                    Apply to Form
                  </button>
                  {assistantRawResult && (
                    <details className="mt-3">
                      <summary className="cursor-pointer text-xs text-gray-500 dark:text-gray-400">Show raw worker output</summary>
                      <pre className="mt-2 bg-gray-50 dark:bg-gray-800 p-2 rounded text-xs whitespace-pre-wrap break-words">{assistantRawResult}</pre>
                    </details>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="bg-white dark:bg-gray-900 shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Basic Information</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Name *
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="My Scheduled Task"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                rows={3}
                placeholder="What does this cronjob do?"
              />
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="enabled"
                checked={formData.enabled}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                className="h-4 w-4 text-indigo-600 dark:text-indigo-400 focus:ring-indigo-500 border-gray-300 dark:border-gray-600 rounded"
              />
              <label htmlFor="enabled" className="ml-2 block text-sm text-gray-900 dark:text-gray-100">
                Enabled
              </label>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-900 shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Schedule</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Cron Expression *
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  required
                  value={formData.cron_expression}
                  onChange={(e) => setFormData({ ...formData, cron_expression: e.target.value })}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
                  placeholder="*/5 * * * *"
                />
              </div>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Format: minute hour day month weekday (e.g., &quot;*/5 * * * *&quot; = every 5 minutes)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Presets
              </label>
              <div className="flex flex-wrap gap-2">
                {cronPresets.map((preset) => (
                  <button
                    key={preset.value}
                    type="button"
                    onClick={() => setFormData({ ...formData, cron_expression: preset.value })}
                    className="px-3 py-1 text-xs bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 rounded-full text-gray-700 dark:text-gray-300"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            {previewRuns.length > 0 && (
              <div className="bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 rounded-md p-4">
                <div className="flex items-center text-blue-800 dark:text-blue-300 mb-2">
                  <Clock className="w-4 h-4 mr-2" />
                  <span className="font-medium">Next 5 runs:</span>
                </div>
                <ul className="text-sm text-blue-700 dark:text-blue-300 space-y-1">
                  {previewRuns.map((run, i) => (
                    <li key={i}>{new Date(run).toLocaleString()}</li>
                  ))}
                </ul>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Timezone
              </label>
              <select
                value={formData.timezone}
                onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="UTC">UTC</option>
                <option value="America/New_York">America/New_York</option>
                <option value="America/Chicago">America/Chicago</option>
                <option value="America/Denver">America/Denver</option>
                <option value="America/Los_Angeles">America/Los_Angeles</option>
                <option value="Europe/London">Europe/London</option>
                <option value="Europe/Paris">Europe/Paris</option>
                <option value="Asia/Tokyo">Asia/Tokyo</option>
              </select>
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-900 shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Task Configuration</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Task Title
              </label>
              <input
                type="text"
                value={formData.task_template.title}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    task_template: { ...formData.task_template, title: e.target.value },
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Automated task"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Prompt *
              </label>
              <textarea
                required
                value={formData.task_template.prompt}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    task_template: { ...formData.task_template, prompt: e.target.value },
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                rows={5}
                placeholder="What should the agent do?"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Codebase ID
              </label>
              <input
                type="text"
                value={formData.task_template.codebase_id}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    task_template: { ...formData.task_template, codebase_id: e.target.value },
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Optional codebase ID"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Agent Type
              </label>
              <select
                value={formData.task_template.agent_type}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    task_template: { ...formData.task_template, agent_type: e.target.value },
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="default">Default</option>
                <option value="explorer">Explorer</option>
                <option value="builder">Builder</option>
                <option value="reviewer">Reviewer</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex justify-end space-x-4">
          <Link
            href="/cronjobs"
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            <Save className="w-5 h-5 mr-2" />
            {saving ? 'Saving...' : 'Save Cronjob'}
          </button>
        </div>
      </form>
    </div>
  );
}
