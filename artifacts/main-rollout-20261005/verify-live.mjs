import assert from 'node:assert/strict';
import fs from 'node:fs';
const directory = new URL('./', import.meta.url);
const read = (name) => JSON.parse(fs.readFileSync(new URL(name, directory), 'utf8'));
const revision = 'eb2051a212a2c729a7963da8e1dda39a4e958513';
const server = read('server-release.json');
const dashboard = read('dashboard-release.json');
for (const release of [server, dashboard]) assert.equal(release.sourceRevision, revision);
const applications = read('argo-live.json').items;
for (const application of applications) {
  assert.equal(application.status.sync.revision, revision);
  assert.equal(application.status.health.status, 'Healthy');
  assert.equal(application.status.operationState.phase, 'Succeeded');
  const drift = application.status.resources.filter((item) => item.status !== 'Synced');
  if (application.metadata.name === 'codetether-marketing') assert.equal(drift.length, 0);
  else assert.ok(drift.every((item) => item.kind === 'StatefulSet' && item.name === 'a2a-server-harvester'));
}
for (const deployment of read('server-deployments.json').items) {
  assert.equal(deployment.status.readyReplicas, deployment.spec.replicas);
  assert.equal(deployment.status.updatedReplicas, deployment.spec.replicas);
  assert.equal(deployment.spec.template.spec.containers[0].image, server.image);
}
const serverPods = read('server-pods.json').items.filter((pod) => /deployment-green|temporal-worker/.test(pod.metadata.name) && !pod.metadata.deletionTimestamp);
const dashboardPods = read('dashboard-pods.json').items.filter((pod) => !pod.metadata.deletionTimestamp);
assert.equal(serverPods.length, 3);
assert.equal(dashboardPods.length, 1);
for (const [pods, release] of [[serverPods, server], [dashboardPods, dashboard]]) {
  for (const pod of pods) {
    assert.equal(pod.status.phase, 'Running');
    for (const container of pod.status.containerStatuses) {
      assert.equal(container.ready, true);
      assert.equal(container.restartCount, 0);
      assert.equal(container.imageID, release.digest);
    }
  }
}
const smoke = [];
for (const [url, expectedStatus] of [['https://api.codetether.run/health', 200], ['https://codetether.run/', 200], ['https://codetether.run/login', 200], ['https://api.codetether.run/v1/worker/connected', 401]]) {
  const response = await fetch(url, { signal: AbortSignal.timeout(30000) });
  const body = await response.text();
  assert.equal(response.status, expectedStatus, url);
  if (url.endsWith('/health')) assert.equal(JSON.parse(body).status, 'healthy');
  smoke.push({ url, expectedStatus, actualStatus: response.status });
}
const result = { level: 'live deployment/Argo', observedAt: new Date().toISOString(), sourceRevision: revision, serverDigest: server.digest, dashboardDigest: dashboard.digest, readyServerPods: serverPods.map((pod) => pod.metadata.name), readyDashboardPods: dashboardPods.map((pod) => pod.metadata.name), applications: applications.map((item) => ({ name: item.metadata.name, namespace: item.metadata.namespace, sync: item.status.sync.status, health: item.status.health.status, revision: item.status.sync.revision })), smoke };
fs.writeFileSync(new URL('live-verification.json', directory), `${JSON.stringify(result, null, 2)}\n`);