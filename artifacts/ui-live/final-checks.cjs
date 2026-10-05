module.exports = async function finalChecks({ page, api, apiBase, evidence, save, safe, out }) {
  const path = require('node:path');
  evidence.finalChecks = [];
  const chat = await api(apiBase + '/v1/agent/tasks/ba84c696-4cbf-4848-af75-c606a6d12d59');
  evidence.finalChecks.push({ flow: 'owned chat session metadata', status: chat.status,
    taskId: chat.data?.id, sessionId: chat.data?.session_id, workspaceId: chat.data?.workspace_id,
    metadataKeys: Object.keys(chat.data?.metadata || {}) }); save();
  if (chat.data?.workspace_id && chat.data?.session_id) {
    const history = await api(apiBase + '/v1/agent/workspaces/' + encodeURIComponent(chat.data.workspace_id) + '/sessions/' + encodeURIComponent(chat.data.session_id) + '/messages?limit=20');
    evidence.finalChecks.push({ flow: 'owned chat history', status: history.status,
      containsExpectedReply: JSON.stringify(history.data).includes('UI_LIVE_CB1E678F_CHAT') }); save();
  }
  for (const endpoint of ['/v1/agent/vault/status', '/v1/agent/api-keys', '/v1/users/me']) {
    const response = await api(apiBase + endpoint);
    const data = response.data || {};
    evidence.finalChecks.push({ endpoint, status: response.status,
      detail: safe(data.detail || data.error || ''),
      ...(endpoint.endsWith('/me') ? { userId: data.id, tasksLimit: data.tasks_limit } : {}) });
    save();
  }
  const response = await api(apiBase + '/v1/agent/tasks');
  const tasks = Array.isArray(response.data) ? response.data : response.data?.tasks || [];
  const ours = tasks.find(task => task.title === 'UI_LIVE_CB1E678F task validation');
  evidence.finalChecks.push({ flow: 'dispatch recovery lookup', status: response.status,
    task: ours ? { id: ours.id, status: ours.status, title: ours.title } : null }); save();
  if (ours) {
    const dispatched = await api(apiBase + '/v1/tasks/dispatch/' + ours.id);
    evidence.finalChecks.push({ flow: 'dispatch persisted status', status: dispatched.status,
      taskId: ours.id, state: dispatched.data?.status, containsExpectedResult: String(dispatched.data?.result || '').includes('UI_LIVE_CB1E678F_TASK'), detail: safe(dispatched.data?.detail || '') }); save();
    const fs = require('node:fs'); const ledgerPath = path.join(out, 'created-tasks.json');
    const ledger = fs.existsSync(ledgerPath) ? JSON.parse(fs.readFileSync(ledgerPath)) : {};
    ledger.dispatch = { id: ours.id, recoveredAfterError: true }; fs.writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2));
    if (['pending', 'queued'].includes(dispatched.data?.status)) {
      // Cancel only this run's exact orphaned nonce task, preserving its record.
      const cancelled = await api(apiBase + '/v1/agent/tasks/' + ours.id + '/cancel', 'POST', {});
      const after = await api(apiBase + '/v1/tasks/dispatch/' + ours.id);
      evidence.finalChecks.push({ flow: 'owned test task cleanup', taskId: ours.id,
        cancelStatus: cancelled.status, finalStatus: after.data?.status }); save();
    }
  }
  if (ours?.status === 'completed') {
    await page.goto('http://localhost:3001/dashboard/tasks', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /UI_LIVE_CB1E678F task validation/ }).click({ timeout: 20000 });
    const result = page.locator('#task-details').getByText('UI_LIVE_CB1E678F_TASK', { exact: true });
    await result.waitFor({ timeout: 20000 });
    evidence.finalChecks.push({ flow: 'real dispatched task result visible', taskId: ours.id, visible: true }); save();
    await page.screenshot({ path: path.join(out, 'verified-task-result.png'), fullPage: true });
  }
  for (const route of ['/dashboard/settings', '/dashboard/billing']) {
    await page.goto('http://localhost:3001' + route, { waitUntil: 'domcontentloaded' });
    await page.getByText('Enterprise', { exact: true }).first().waitFor({ timeout: 20000 });
    const usage = page.getByText(/\d+ \/ Unlimited/).first();
    await usage.waitFor({ timeout: 20000 });
    evidence.finalChecks.push({ flow: 'live billing contract displayed', route,
      enterpriseVisible: true, usage: await usage.innerText(), alerts: (await page.getByRole('alert').allTextContents()).map(safe) });
    await page.screenshot({ path: path.join(out, 'verified-' + route.split('/').pop() + '.png'), fullPage: true }); save();
  }
};