// Controlled live writes: two marked, no-tools nonce responses. No payments.
const fs = require('node:fs');
const path = require('node:path');
module.exports = async function run({ page, api, apiBase, evidence, save, safe, out }) {
  const marker = 'UI_LIVE_CB1E678F';
  const ledgerPath = path.join(out, 'created-tasks.json');
  const ledger = fs.existsSync(ledgerPath) ? JSON.parse(fs.readFileSync(ledgerPath)) : {};
  const persist = () => fs.writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2));
  async function poll(id, endpoint, expected, seconds = 240) {
    const states = [];
    const end = Date.now() + seconds * 1000;
    while (Date.now() < end) {
      const response = await api(apiBase + endpoint + id);
      const data = response.data || {};
      const status = data.status || data.state;
      states.push({ at: new Date().toISOString(), httpStatus: response.status, status });
      if (['completed', 'failed', 'cancelled', 'timed_out', 'error'].includes(status)) {
        return { status, states, model: data.model || data.model_ref || null, worker: data.worker_id || data.assigned_worker_id || null,
          containsExpectedResult: JSON.stringify(data.result || data.output || '').includes(expected),
          error: data.error ? safe(typeof data.error === 'string' ? data.error : JSON.stringify(data.error)) : null };
      }
      await page.waitForTimeout(5000);
    }
    return { status: 'poll-timeout', states };
  }
  async function screenshot(name) { await page.screenshot({ path: path.join(out, name), fullPage: true }); }
  evidence.mutations = [];
  // Exercise the real worker chat route and its explicit model selection.
  try {
    const record = { flow: 'workers chat', requestedWorker: 'harvester-a2a-server-harvester-1' };
    evidence.mutations.push(record); save();
    await page.goto('http://localhost:3001/dashboard/workers', { waitUntil: 'domcontentloaded' });
    const name = page.getByRole('heading', { name: record.requestedWorker, exact: true }).first();
    const card = name.locator('xpath=ancestor::div[.//button[normalize-space()="Chat via SSE"]][1]');
    await card.getByRole('button', { name: 'Chat via SSE', exact: true }).click({ timeout: 30000 });
    if (!ledger.chat) {
      const previous = await api(apiBase + '/v1/agent/tasks');
      const tasks = Array.isArray(previous.data) ? previous.data : previous.data?.tasks || [];
      const existing = tasks.find(task => String(task.title || '').includes(marker + '_CHAT'));
      if (existing) {
        ledger.chat = { id: existing.id, requestedModel: existing.model_ref || existing.model, worker: existing.worker_id };
        persist();
      }
    }
    if (!ledger.chat) {
      const model = page.getByRole('combobox', { name: 'Model', exact: true });
      await model.fill('openai-codex/gpt-5.5-fast');
      const option = page.getByRole('option').filter({ hasText: 'gpt-5.5-fast' }).filter({ hasText: 'Codex' }).first();
      await option.click({ timeout: 15000 });
      const responsePromise = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/v1/agent/tasks'), { timeout: 45000 });
      await page.getByPlaceholder('Message this worker...').fill(`Read-only UI integration check. Reply exactly ${marker}_CHAT. Do not call tools, read files/history, access the network, spawn agents, or modify anything.`);
      await page.getByRole('button', { name: 'Send', exact: true }).click();
      const response = await responsePromise;
      const data = await response.json();
      const request = response.request().postDataJSON();
      record.httpStatus = response.status();
      record.requestedModel = request.model_ref;
      record.agentType = request.agent_type;
      if (!response.ok() || !data.id) throw new Error(`Worker chat creation returned ${response.status()}: ${safe(JSON.stringify(data))}`);
      ledger.chat = { id: data.id, requestedModel: request.model_ref, worker: request.metadata?.target_worker_id };
      persist();
    }
    record.task = ledger.chat; save();
    record.outcome = await poll(ledger.chat.id, '/v1/agent/tasks/', marker + '_CHAT');
    if (record.outcome.status === 'completed' && !record.outcome.containsExpectedResult) {
      const output = await api(apiBase + '/v1/agent/tasks/' + ledger.chat.id + '/output');
      record.outputStatus = output.status;
      record.outputContainsExpectedResult = JSON.stringify(output.data).includes(marker + '_CHAT');
    }
    record.uiResponseVisible = await page.getByText(marker + '_CHAT', { exact: true }).isVisible().catch(() => false);
    await screenshot('live-worker-chat.png'); save();
  } catch (error) {
    evidence.mutations.at(-1).error = safe(error.message); save();
    await screenshot('live-worker-chat-error.png').catch(() => {});
  }
  // Exercise the Tasks page's distinct dispatch endpoint, once only.
  try {
    const record = { flow: 'tasks dispatch', title: marker + ' task validation', requestedAgentType: 'plan' };
    evidence.mutations.push(record); save();
    await page.goto('http://localhost:3001/dashboard/tasks', { waitUntil: 'domcontentloaded' });
    if (!ledger.dispatch) {
      // Do not duplicate a request accepted during an earlier interrupted run.
      const list = await api(apiBase + '/v1/agent/tasks');
      const tasks = Array.isArray(list.data) ? list.data : list.data?.tasks || [];
      const existing = tasks.find(task => task.title === record.title);
      if (existing) { ledger.dispatch = { id: existing.id }; persist(); }
    }
    if (!ledger.dispatch) {
      await page.getByRole('button', { name: 'New Task', exact: true }).click();
      const dialog = page.getByRole('dialog', { name: 'Create New Task' });
      await dialog.getByLabel('Title', { exact: true }).fill(record.title);
      await dialog.getByLabel('Description', { exact: true }).fill(`Read-only UI integration check. Reply exactly ${marker}_TASK. Do not call tools, read files/history, access the network, spawn agents, or modify anything.`);
      await dialog.getByLabel('Agent Type', { exact: true }).selectOption('plan');
      const responsePromise = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/v1/tasks/dispatch'), { timeout: 45000 });
      await dialog.getByRole('button', { name: 'Dispatch Task', exact: true }).click();
      const response = await responsePromise;
      const data = await response.json();
      record.httpStatus = response.status();
      if (!response.ok() || !data.task_id) throw new Error(`Task dispatch returned ${response.status()}: ${safe(JSON.stringify(data))}`);
      ledger.dispatch = { id: data.task_id, eventId: data.event_id || null, knative: data.dispatched_via_knative };
      persist();
    }
    record.task = ledger.dispatch; save();
    record.outcome = await poll(ledger.dispatch.id, '/v1/tasks/dispatch/', marker + '_TASK');
    await screenshot('live-dispatched-task.png'); save();
  } catch (error) {
    evidence.mutations.at(-1).error = safe(error.message); save();
    await screenshot('live-dispatched-task-error.png').catch(() => {});
  }
};