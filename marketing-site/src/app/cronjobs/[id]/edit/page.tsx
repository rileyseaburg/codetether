'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Save, Clock, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { useTenantApi } from '@/hooks/useTenantApi';

interface Props {
  params: { id: string };
}

export default function EditCronjobPage({ params }: Props) {
  const router = useRouter();
  const { tenantFetch } = useTenantApi();
  const isNew = params.id === 'new';
  
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

  useEffect(() => {
    if (!isNew) {
      fetchJob();
    }
  }, [isNew]);

  useEffect(() => {
    if (formData.cron_expression) {
      validateAndPreview();
    }
  }, [formData.cron_expression, formData.timezone]);

  async function fetchJob() {
    try {
      const { data, error } = await tenantFetch<any>(`/v1/cronjobs/${params.id}`);
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const url = isNew ? '/v1/cronjobs' : `/v1/cronjobs/${params.id}`;
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
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center mb-6">
        <Link
          href="/cronjobs"
          className="inline-flex items-center text-gray-600 hover:text-gray-900 mr-4"
        >
          <ArrowLeft className="w-5 h-5 mr-2" />
          Back
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">
          {isNew ? 'Create Cronjob' : 'Edit Cronjob'}
        </h1>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded flex items-center">
          <AlertCircle className="w-5 h-5 mr-2" />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Basic Information</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Name *
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="My Scheduled Task"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
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
                className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
              />
              <label htmlFor="enabled" className="ml-2 block text-sm text-gray-900">
                Enabled
              </label>
            </div>
          </div>
        </div>

        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Schedule</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Cron Expression *
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  required
                  value={formData.cron_expression}
                  onChange={(e) => setFormData({ ...formData, cron_expression: e.target.value })}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
                  placeholder="*/5 * * * *"
                />
              </div>
              <p className="mt-1 text-xs text-gray-500">
                Format: minute hour day month weekday (e.g., &quot;*/5 * * * *&quot; = every 5 minutes)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Presets
              </label>
              <div className="flex flex-wrap gap-2">
                {cronPresets.map((preset) => (
                  <button
                    key={preset.value}
                    type="button"
                    onClick={() => setFormData({ ...formData, cron_expression: preset.value })}
                    className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded-full text-gray-700"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            {previewRuns.length > 0 && (
              <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                <div className="flex items-center text-blue-800 mb-2">
                  <Clock className="w-4 h-4 mr-2" />
                  <span className="font-medium">Next 5 runs:</span>
                </div>
                <ul className="text-sm text-blue-700 space-y-1">
                  {previewRuns.map((run, i) => (
                    <li key={i}>{new Date(run).toLocaleString()}</li>
                  ))}
                </ul>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Timezone
              </label>
              <select
                value={formData.timezone}
                onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
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

        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Task Configuration</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
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
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Automated task"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
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
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                rows={5}
                placeholder="What should the agent do?"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
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
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Optional codebase ID"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
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
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
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
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
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
