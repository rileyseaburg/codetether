'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Calendar, Clock, Edit, Pause, Play, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
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
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled' | 'attention'>('all');

  useEffect(() => {
    void fetchJobs(true);
  }, []);

  async function fetchJobs(showSpinner = false) {
    if (showSpinner) {
      setRefreshing(true);
    }

    try {
      const { data, error } = await tenantFetch<{ items?: Cronjob[] }>('/v1/cronjobs');
      if (error) throw new Error(error);
      setJobs(data?.items || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cronjobs');
    } finally {
      setLoading(false);
      if (showSpinner) {
        setRefreshing(false);
      }
    }
  }

  async function toggleJob(id: string) {
    setActiveAction(`toggle:${id}`);
    setActionError(null);

    try {
      const { error } = await tenantFetch(`/v1/cronjobs/${id}/toggle`, {
        method: 'POST',
      });
      if (error) throw new Error(error);
      await fetchJobs();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to toggle');
    } finally {
      setActiveAction(null);
    }
  }

  async function triggerJob(id: string) {
    setActiveAction(`trigger:${id}`);
    setActionError(null);

    try {
      const { error } = await tenantFetch(`/v1/cronjobs/${id}/trigger`, {
        method: 'POST',
      });
      if (error) throw new Error(error);
      await fetchJobs();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to trigger');
    } finally {
      setActiveAction(null);
    }
  }

  async function deleteJob(id: string, name: string) {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;

    setActiveAction(`delete:${id}`);
    setActionError(null);

    try {
      const { error } = await tenantFetch(`/v1/cronjobs/${id}`, {
        method: 'DELETE',
      });
      if (error) throw new Error(error);
      await fetchJobs();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete');
    } finally {
      setActiveAction(null);
    }
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

  function formatDateTime(date: string | null): string {
    if (!date) return 'Never';
    return new Date(date).toLocaleString();
  }

  function formatRelative(date: string | null): string {
    if (!date) return '-';
    const time = new Date(date).getTime();
    const delta = time - Date.now();
    const abs = Math.abs(delta);
    const minutes = Math.round(abs / 60000);
    const hours = Math.round(abs / 3600000);
    const days = Math.round(abs / 86400000);

    if (minutes < 1) return 'now';
    if (minutes < 60) return delta >= 0 ? `in ${minutes}m` : `${minutes}m ago`;
    if (hours < 24) return delta >= 0 ? `in ${hours}h` : `${hours}h ago`;
    return delta >= 0 ? `in ${days}d` : `${days}d ago`;
  }

  const filteredJobs = useMemo(() => {
    const queryValue = query.trim().toLowerCase();
    return jobs.filter((job) => {
      const matchesQuery =
        !queryValue ||
        job.name.toLowerCase().includes(queryValue) ||
        (job.description || '').toLowerCase().includes(queryValue) ||
        job.cron_expression.toLowerCase().includes(queryValue);

      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'enabled' && job.enabled) ||
        (statusFilter === 'disabled' && !job.enabled) ||
        (statusFilter === 'attention' && job.error_count > 0);

      return matchesQuery && matchesStatus;
    });
  }, [jobs, query, statusFilter]);

  const enabledCount = jobs.filter((job) => job.enabled).length;
  const attentionCount = jobs.filter((job) => job.error_count > 0).length;

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
        <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-4 py-3 rounded">
          Error: {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto text-gray-900 dark:text-gray-100">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Cronjobs</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Schedule and manage automated tasks</p>
        </div>
        <Link
          href="/cronjobs/new/edit"
          className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Plus className="w-5 h-5 mr-2" />
          Create Cronjob
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Total jobs</p>
          <p className="text-xl font-semibold text-gray-900 dark:text-gray-100">{jobs.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Enabled</p>
          <p className="text-xl font-semibold text-green-700 dark:text-green-300">{enabledCount}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Needs attention</p>
          <p className="text-xl font-semibold text-red-700 dark:text-red-300">{attentionCount}</p>
        </div>
      </div>

      <div className="bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 rounded-lg px-4 py-3 mb-4 text-sm text-blue-900 dark:text-blue-200">
        A job runs only when it is <strong>Enabled</strong>. Use <strong>Run now</strong> for manual execution,
        and check <strong>Next run</strong> to confirm scheduling.
      </div>

      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-3 mb-4">
        <div className="flex flex-col md:flex-row md:items-center gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-gray-400 dark:text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by name, description, or cron expression"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-md pl-9 pr-3 py-2 text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
            className="border border-gray-300 dark:border-gray-600 rounded-md px-3 py-2 text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">All statuses</option>
            <option value="enabled">Enabled</option>
            <option value="disabled">Disabled</option>
            <option value="attention">Needs attention</option>
          </select>
          <button
            onClick={() => void fetchJobs(true)}
            className="inline-flex items-center justify-center px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
            disabled={refreshing}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {actionError && (
        <div className="mb-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-4 py-3 rounded">
          {actionError}
        </div>
      )}

      {jobs.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <Clock className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No cronjobs yet</h3>
          <p className="text-gray-600 dark:text-gray-400 mb-4">Create your first scheduled task to get started</p>
          <Link
            href="/cronjobs/new/edit"
            className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            <Plus className="w-5 h-5 mr-2" />
            Create Cronjob
          </Link>
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No matching cronjobs</h3>
          <p className="text-gray-600 dark:text-gray-400 mb-4">Try clearing filters or search terms.</p>
          <button
            onClick={() => {
              setQuery('');
              setStatusFilter('all');
            }}
            className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 shadow rounded-lg overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Schedule
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Last Run
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Next Run
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Activity
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
              {filteredJobs.map((job) => (
                <tr key={job.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                  <td className="px-6 py-4">
                    <div>
                      <Link
                        href={`/cronjobs/${job.id}`}
                        className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-900 dark:hover:text-indigo-300"
                      >
                        {job.name}
                      </Link>
                      {job.description && (
                        <p className="text-sm text-gray-500 dark:text-gray-400">{job.description}</p>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center text-sm text-gray-900 dark:text-gray-100">
                      <Calendar className="w-4 h-4 mr-2 text-gray-400 dark:text-gray-500" />
                      <code className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-xs">
                        {job.cron_expression}
                      </code>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {formatCronExpression(job.cron_expression)}
                    </p>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        job.enabled
                          ? 'bg-green-100 text-green-800 dark:text-green-300'
                          : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
                      }`}
                    >
                      {job.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                    {job.error_count > 0 && (
                      <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:text-red-300">
                        {job.error_count} errors
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                    <p>{formatDateTime(job.last_run_at)}</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">{formatRelative(job.last_run_at)}</p>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                    <p>{job.next_run_at ? formatDateTime(job.next_run_at) : 'Not scheduled'}</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      {job.next_run_at ? formatRelative(job.next_run_at) : job.enabled ? 'Waiting for schedule' : 'Disabled'}
                    </p>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                    <p>{job.run_count} total runs</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">{job.error_count} errors</p>
                  </td>
                  <td className="px-6 py-4 text-right text-sm font-medium">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => void triggerJob(job.id)}
                        className="inline-flex items-center px-2.5 py-1.5 border border-indigo-200 text-indigo-700 dark:text-indigo-300 rounded hover:bg-indigo-50 disabled:opacity-50"
                        disabled={activeAction !== null}
                      >
                        <Play className="w-3.5 h-3.5 mr-1" />
                        Run now
                      </button>
                      <button
                        onClick={() => void toggleJob(job.id)}
                        className="inline-flex items-center px-2.5 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
                        disabled={activeAction !== null}
                      >
                        {job.enabled ? (
                          <>
                            <Pause className="w-3.5 h-3.5 mr-1" />
                            Pause
                          </>
                        ) : (
                          <>
                            <Play className="w-3.5 h-3.5 mr-1" />
                            Enable
                          </>
                        )}
                      </button>
                      <Link
                        href={`/cronjobs/${job.id}/edit`}
                        className="inline-flex items-center px-2.5 py-1.5 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-50 dark:hover:bg-gray-800"
                      >
                        <Edit className="w-3.5 h-3.5 mr-1" />
                        Edit
                      </Link>
                      <button
                        onClick={() => void deleteJob(job.id, job.name)}
                        className="inline-flex items-center px-2.5 py-1.5 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 rounded hover:bg-red-50 dark:bg-red-950/40 disabled:opacity-50"
                        disabled={activeAction !== null}
                      >
                        <Trash2 className="w-3.5 h-3.5 mr-1" />
                        Delete
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
