#!/usr/bin/env node
// Read-only diagnosis of current iOS-originated failures, not saved agent history.
const fs = require('node:fs');
require('node:dns').setDefaultResultOrder('ipv4first');
async function main() {
  const token = fs.readFileSync('/etc/codetether-worker/env', 'utf8').split('\n')
    .find(line => line.startsWith('CODETETHER_TOKEN=')).slice(17).replace(/^["']|["']$/g, '');
  async function get(route) {
    const response = await fetch('https://api.codetether.run' + route, {
      headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(20000) });
    if (!response.ok) throw new Error(`API HTTP ${response.status}`);
    const bytes = Buffer.from(await response.arrayBuffer());
    if (bytes.length > 8_000_000) throw new Error('Response exceeds diagnostic bound');
    return JSON.parse(bytes.toString());
  }
  const redact = text => String(text || '').split(token).join('[redacted]')
    .replace(/Bearer\s+[^\s"']+/gi, 'Bearer [redacted]')
    .replace(/((?:api[_-]?key|access[_-]?token|password)\s*[=:]\s*)[^\s,}]+/gi, '$1[redacted]').slice(0, 5000);
  const workers = await get('/v1/agent/workers?online_only=true');
  const selected = workers.filter(w => w.capabilities?.includes('session-context'));
  const errors = [];
  for (const worker of selected) {
    const tasks = await get(`/v1/agent/tasks?status=failed&worker_id=${encodeURIComponent(worker.worker_id)}`);
    for (const task of tasks) {
      const metadata = typeof task.metadata === 'string' ? JSON.parse(task.metadata) : task.metadata || {};
      if (!String(metadata.context_id || '').startsWith('ios-')) continue;
      if (Date.parse(task.created_at) < Date.now() - 6 * 3600000) continue;
      errors.push({ taskId: task.id, status: task.status, createdAt: task.created_at,
        workerId: worker.worker_id, workspaceId: task.workspace_id || task.codebase_id,
        model: task.model, modelRef: task.model_ref || metadata.model_ref,
        selectedModel: metadata.model || metadata.selected_model, targetWorkerId: metadata.target_worker_id,
        error: redact(task.error), diagnostics: metadata.diagnostics ? Object.keys(metadata.diagnostics) : [] });
    }
  }
  const report = { observedAt: new Date().toISOString(), level: 'live deployment/Argo', errors,
    workers: selected.map(w => ({ id: w.worker_id, name: w.name, status: w.status,
      modelCount: w.models?.length || 0, models: (w.models || []).map(m => typeof m === 'string'
        ? { id: m } : { id: m.id, name: m.name, providerId: m.provider_id || m.provider,
          available: m.available, configured: m.configured }) })) };
  const directory = 'artifacts/agent-workflow-validation/app-api-repair';
  fs.mkdirSync(directory, { recursive: true });
  const output = `${directory}/inspection-${Date.now()}.json`;
  fs.writeFileSync(output, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ artifact: output, errors, workers: report.workers.map(w => ({
    id: w.id, name: w.name, modelCount: w.modelCount,
    providers: [...new Set(w.models.map(m => m.providerId || m.id.split('/')[0]))],
    relevantModels: w.models.filter(m => /gpt-5-mini|codetether|codex/i.test(m.id)).slice(0, 18),
  })) }, null, 2));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });