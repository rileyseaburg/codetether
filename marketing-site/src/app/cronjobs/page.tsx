'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Clock, Plus, Play, Pause, Trash2, Edit, Calendar } from 'lucide-react';
import { useTenantApi } from '@/hooks/useTenantApi';

interface Cronjob {
  id: string;
  name: string;
  description: string | null;
  cron_expression: string;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  run_count: number;
  error_count: number;
  created_at: string;
}

export default function CronjobsPage() {
  const { tenantFetch } = useTenantApi();
  const [jobs, setJobs] = useState<Cronjob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJobs();
  }, []);

  async function fetchJobs() {
    try {
      const { data, error } = await tenantFetch<{ items?: Cronjob[] }>('/v1/cronjobs');
      if (error) throw new Error(error);
      setJobs(data?.items || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cronjobs');
    } finally {
      setLoading(false);
    }
  }

  async function toggleJob(id: string) {
    try {
      const { error } = await tenantFetch(`/v1/cronjobs/${id}/toggle`, {
        method: 'POST',
      });
      if (error) throw new Error(error);
      fetchJobs();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to toggle');
    }
  }

  async function triggerJob(id: string) {
    try {
      const { error } = await tenantFetch(`/v1/cronjobs/${id}/trigger`, {
        method: 'POST',
      });
      if (error) throw new Error(error);
      alert('Job triggered successfully!');
      fetchJobs();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to trigger');
    }
  }

  async function deleteJob(id: string) {
    if (!confirm('Are you sure you want to delete this cronjob?')) return;
    
    try {
      const { error } = await tenantFetch(`/v1/cronjobs/${id}`, {
        method: 'DELETE',
      });
      if (error) throw new Error(error);
      fetchJobs();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete');
    }
  }

  function formatCronExpression(expr: string): string {
    // Simple human-readable format
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

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          Error: {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Cronjobs</h1>
          <p className="text-gray-600 mt-1">Schedule and manage automated tasks</p>
        </div>
        <Link
          href="/cronjobs/new/edit"
          className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Plus className="w-5 h-5 mr-2" />
          Create Cronjob
        </Link>
      </div>

      {jobs.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <Clock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No cronjobs yet</h3>
          <p className="text-gray-600 mb-4">Create your first scheduled task to get started</p>
          <Link
            href="/cronjobs/new/edit"
            className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            <Plus className="w-5 h-5 mr-2" />
            Create Cronjob
          </Link>
        </div>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Schedule
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Run
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Next Run
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Runs
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {jobs.map((job) => (
                <tr key={job.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div>
                      <Link
                        href={`/cronjobs/${job.id}`}
                        className="text-sm font-medium text-indigo-600 hover:text-indigo-900"
                      >
                        {job.name}
                      </Link>
                      {job.description && (
                        <p className="text-sm text-gray-500">{job.description}</p>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center text-sm text-gray-900">
                      <Calendar className="w-4 h-4 mr-2 text-gray-400" />
                      <code className="bg-gray-100 px-2 py-1 rounded text-xs">
                        {job.cron_expression}
                      </code>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatCronExpression(job.cron_expression)}
                    </p>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        job.enabled
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {job.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                    {job.error_count > 0 && (
                      <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        {job.error_count} errors
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {job.last_run_at
                      ? new Date(job.last_run_at).toLocaleString()
                      : 'Never'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {job.next_run_at
                      ? new Date(job.next_run_at).toLocaleString()
                      : 'Not scheduled'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {job.run_count}
                  </td>
                  <td className="px-6 py-4 text-right text-sm font-medium">
                    <div className="flex justify-end space-x-2">
                      <button
                        onClick={() => triggerJob(job.id)}
                        className="text-indigo-600 hover:text-indigo-900 p-1"
                        title="Run now"
                      >
                        <Play className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => toggleJob(job.id)}
                        className="text-gray-600 hover:text-gray-900 p-1"
                        title={job.enabled ? 'Disable' : 'Enable'}
                      >
                        {job.enabled ? (
                          <Pause className="w-4 h-4" />
                        ) : (
                          <Play className="w-4 h-4" />
                        )}
                      </button>
                      <Link
                        href={`/cronjobs/${job.id}/edit`}
                        className="text-indigo-600 hover:text-indigo-900 p-1"
                        title="Edit"
                      >
                        <Edit className="w-4 h-4" />
                      </Link>
                      <button
                        onClick={() => deleteJob(job.id)}
                        className="text-red-600 hover:text-red-900 p-1"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
