#!/usr/bin/env node
// Register a confirmed local workspace; deliberately never submit an agent task.
const fs = require('node:fs');
const path = require('node:path');
const workspaceId = 'ios-e2e-ubuntu-dev';
const workerId = 'wrk_1791203157_35195f4f7b97da0a';
const userId = '0f3ebd9f-c68a-4b86-97a5-442d4fc62880';
const directory = path.resolve(__dirname, '../artifacts/ios-e2e-web');
async function main() {
  const env = fs.readFileSync('/etc/codetether-worker/env', 'utf8');
  const entry = env.split('\n').find(line => line.startsWith('CODETETHER_TOKEN='));
  if (!entry) throw new Error('Worker credential unavailable');
  const token = entry.slice('CODETETHER_TOKEN='.length).replace(/^["']|["']$/g, '');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  async function request(route, method = 'GET', body) {
    const response = await fetch(`https://api.codetether.run${route}`, {
      method, headers, ...(body ? { body: JSON.stringify(body) } : {}),
      signal: AbortSignal.timeout(30000),
    });
    if (!response.ok) throw new Error(`${method} ${route}: HTTP ${response.status}`);
    return response.json();
  }
  const listing = await request('/v1/agent/workers');
  const workers = Array.isArray(listing) ? listing : listing.workers;
  if (!workers?.some(worker => worker.worker_id === workerId && worker.name === 'ubuntu-dev')) {
    throw new Error('Expected live local worker is not registered; recheck identity');
  }
  const all = await request('/v1/agent/workspaces');
  const existing = all.find(workspace => workspace.id === workspaceId);
  if (existing && (existing.path !== directory || existing.worker_id !== workerId)) {
    throw new Error('Workspace identity differs; refusing overwrite');
  }
  fs.mkdirSync(directory, { recursive: true });
  if (!existing) await request('/v1/agent/workspaces', 'POST', {
    workspace_id: workspaceId, name: 'iOS E2E - ubuntu-dev', path: directory,
    description: 'Isolated workspace for the user-requested native iPhone HTML test',
    worker_id: workerId,
  });
  const actual = (await request('/v1/agent/workspaces')).find(workspace => workspace.id === workspaceId);
  if (actual?.path !== directory || actual?.worker_id !== workerId) {
    throw new Error('Workspace read-back mismatch');
  }
  const report = { workspaceId, workerId, path: directory, userId,
    intendedDocumentRoot: path.join(directory, 'site'),
    intendedURL: 'http://192.168.50.101:8766/', htmlCreated: false, taskSubmitted: false };
  try {
    await request(`/v1/auth/user/${userId}/workspaces`, 'POST', { workspace_id: workspaceId, role: 'collaborator' });
    report.association = 'created';
  } catch (error) {
    report.association = error.message;
  }
  fs.writeFileSync(path.resolve(__dirname, '../artifacts/ios-login-e2e-20261005/workspace-preflight.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });


