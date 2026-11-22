'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Play, Edit, Trash2, Clock, Calendar, CheckCircle, XCircle } from 'lucide-react';
import { useTenantApi } from '@/hooks/useTenantApi';

interface Props {
  params: Promise<{ id: string }>;
}

interface Cronjob {
  id: string;
  name: string;
  description: string | null;
  cron_expression: string;
  timezone: string;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  run_count: number;
  error_count: number;
  created_at: string;
  updated_at: string;
  task_template: {
    title?: string;
    prompt?: string;
    codebase_id?: string;
    agent_type?: string;
  };
}

interface CronjobRun {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  output: string | null;
  error_message: string | null;
  task_id: string | null;
}

export default function CronjobDetailPage({ params }: Props) {
  const { id } = use(params);
  const router = useRouter();
  const { tenantFetch } = useTenantApi();
  const [job, setJob] = useState<Cronjob | null>(null);
  const [runs, setRuns] = useState<CronjobRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    fetchJob();
    fetchRuns();
  }, [id]);

  async function fetchJob() {
    try {
      const { data, error } = await tenantFetch<Cronjob>(`/v1/cronjobs/${id}`);
      if (error || !data) throw new Error(error || 'Failed to fetch cronjob');
      setJob(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cronjob');
    } finally {
      setLoading(false);
    }
  }

  async function fetchRuns() {
    try {
      const { data, error } = await tenantFetch<{ items?: CronjobRun[] }>(`/v1/cronjobs/${id}/runs`);
      if (error) throw new Error(error);
      setRuns(data?.items || []);
    } catch (err) {
      console.error('Failed to load runs:', err);
    }
  }

  async function triggerJob() {
    setActionLoading(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const { error } = await tenantFetch(`/v1/cronjobs/${id}/trigger`, {
        method: 'POST',
      });
      if (error) throw new Error(error);
      setActionMessage('Run queued successfully.');
      fetchRuns();
      fetchJob();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to trigger');
    } finally {
      setActionLoading(false);
    }
  }

  async function deleteJob() {
    if (!confirm('Are you sure you want to delete this cronjob?')) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const { error } = await tenantFetch(`/v1/cronjobs/${id}`, {
        method: 'DELETE',
      });
      if (error) throw new Error(error);
      router.push('/cronjobs');
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete');
    } finally {
      setActionLoading(false);
    }
  }

  function formatDuration(ms: number | null): string {
    if (!ms) return '-';
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  }

  function formatCronExpression(expr: string): string {
    const parts = expr.split(' ');
    if (parts.length !== 5) return expr;
    
    const [min, hour, day, month, weekday] = parts;
    
    if (min === '0' && hour === '0' && day === '*' && month === '*' && weekday === '*') {
      return 'Daily at midnight';
    }
    if (min === '0' && hour === '*' && day === '*' && month === '*' && weekday === '*') {
      return 'Every hour';
    }
    if (min === '*/5' && hour === '*' && day === '*' && month === '*' && weekday === '*') {
      return 'Every 5 minutes';
    }
    
    return expr;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-4 py-3 rounded">
          Error: {error || 'Cronjob not found'}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto text-gray-900 dark:text-gray-100">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <Link
            href="/cronjobs"
            className="inline-flex items-center text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mr-4"
          >
            <ArrowLeft className="w-5 h-5 mr-2" />
            Back
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{job.name}</h1>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={triggerJob}
            disabled={actionLoading}
            className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            <Play className="w-4 h-4 mr-2" />
            Run Now
          </button>
          <Link
            href={`/cronjobs/${job.id}/edit`}
            className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <Edit className="w-4 h-4 mr-2" />
            Edit
          </Link>
          <button
            onClick={deleteJob}
            disabled={actionLoading}
            className="inline-flex items-center px-4 py-2 border border-red-300 text-red-700 dark:text-red-300 rounded-lg hover:bg-red-50 dark:bg-red-950/40 disabled:opacity-50"
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Delete
          </button>
        </div>
      </div>

      <div className="bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 rounded-lg px-4 py-3 mb-4 text-sm text-blue-900 dark:text-blue-200">
        Use <strong>Run Now</strong> for an immediate execution. Scheduled runs only occur while this cronjob is <strong>Enabled</strong>.
      </div>

      {actionMessage && (
        <div className="mb-4 bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-900 text-green-700 dark:text-green-300 px-4 py-3 rounded">
          {actionMessage}
        </div>
      )}

      {actionError && (
        <div className="mb-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-4 py-3 rounded">
          {actionError}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Job Details */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white dark:bg-gray-900 shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Details</h2>
            
            {job.description && (
              <p className="text-gray-600 dark:text-gray-400 mb-4">{job.description}</p>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">Schedule</span>
                <div className="flex items-center mt-1">
                  <Calendar className="w-4 h-4 mr-2 text-gray-400 dark:text-gray-500" />
                  <code className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-sm">
                    {job.cron_expression}
                  </code>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {formatCronExpression(job.cron_expression)}
                </p>
              </div>

              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">Timezone</span>
                <p className="mt-1 font-medium">{job.timezone}</p>
              </div>

              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">Status</span>
                <p className="mt-1">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      job.enabled
                        ? 'bg-green-100 text-green-800 dark:text-green-300'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
                    }`}
                  >
                    {job.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </p>
              </div>

              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">Next Run</span>
                <p className="mt-1">
                  {job.next_run_at
                    ? new Date(job.next_run_at).toLocaleString()
                    : 'Not scheduled'}
                </p>
              </div>

              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">Last Run</span>
                <p className="mt-1">
                  {job.last_run_at
                    ? new Date(job.last_run_at).toLocaleString()
                    : 'Never'}
                </p>
              </div>

              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">Total Runs</span>
                <p className="mt-1 font-medium">{job.run_count}</p>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-900 shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Execution History</h2>
            
            {runs.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400 text-center py-8">No runs yet</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Status
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Started
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Duration
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Task ID
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                    {runs.map((run) => (
                      <tr key={run.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              run.status === 'completed'
                                ? 'bg-green-100 text-green-800 dark:text-green-300'
                                : run.status === 'failed'
                                ? 'bg-red-100 text-red-800 dark:text-red-300'
                                : run.status === 'running'
                                ? 'bg-blue-100 text-blue-800 dark:text-blue-300'
                                : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
                            }`}
                          >
                            {run.status === 'completed' && (
                              <CheckCircle className="w-3 h-3 mr-1" />
                            )}
                            {run.status === 'failed' && (
                              <XCircle className="w-3 h-3 mr-1" />
                            )}
                            {run.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                          {run.started_at
                            ? new Date(run.started_at).toLocaleString()
                            : '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                          {formatDuration(run.duration_ms)}
                        </td>
                        <td className="px-4 py-3 text-sm font-mono text-gray-500 dark:text-gray-400">
                          {run.task_id ? run.task_id.slice(0, 8) + '...' : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <div className="bg-white dark:bg-gray-900 shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Task Configuration</h2>
            
            <div className="space-y-4">
              {job.task_template.title && (
                <div>
                  <span className="text-sm text-gray-500 dark:text-gray-400">Title</span>
                  <p className="font-medium">{job.task_template.title}</p>
                </div>
              )}

              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">Agent Type</span>
                <p className="font-medium capitalize">{job.task_template.agent_type || 'Default'}</p>
              </div>

              {job.task_template.codebase_id && (
                <div>
                  <span className="text-sm text-gray-500 dark:text-gray-400">Codebase ID</span>
                  <p className="font-mono text-sm">{job.task_template.codebase_id}</p>
                </div>
              )}

              {job.task_template.prompt && (
                <div>
                  <span className="text-sm text-gray-500 dark:text-gray-400">Prompt</span>
                  <p className="text-sm text-gray-700 dark:text-gray-300 mt-1 bg-gray-50 dark:bg-gray-800 p-3 rounded">
                    {job.task_template.prompt}
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="bg-white dark:bg-gray-900 shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Statistics</h2>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">{job.run_count}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">Total Runs</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-red-600">{job.error_count}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">Errors</p>
              </div>
            </div>
          </div>

          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 text-sm text-gray-500 dark:text-gray-400">
            <p>Created: {new Date(job.created_at).toLocaleString()}</p>
            <p className="mt-1">Updated: {new Date(job.updated_at).toLocaleString()}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
